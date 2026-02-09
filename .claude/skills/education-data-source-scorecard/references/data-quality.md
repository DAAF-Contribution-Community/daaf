# Data Quality and Limitations

College Scorecard data has important quality considerations and limitations that affect interpretation. Understanding these issues is critical for valid analysis.

## Privacy Suppression

### Suppression Rules

Scorecard suppresses data when cell sizes are too small:

| Metric Type | Suppression Threshold |
|-------------|----------------------|
| Earnings | < 30 students with positive earnings |
| Completion | < 30 students in cohort |
| Debt | < 30 borrowers |
| Disaggregations | Additional suppression for small cells |

### Why Suppression Exists

1. **Student privacy** - Individuals could be identified
2. **Statistical reliability** - Small samples are noisy
3. **Legal requirements** - Federal privacy regulations

### Suppression Indicators

> **Portal Encoding:** In Portal mirror parquet files, **`null` is the primary indicator** for suppressed/missing data. The codebook documents `-1, -2, -3` codes, but actual parquet data typically uses `null`.

| Data Pattern | Meaning | Notes |
|--------------|---------|-------|
| `null` | Suppressed or missing | Primary indicator in parquet |
| Positive value | Valid data | Actual earnings, counts, etc. |
| `*_SUPP` = 1 | Suppression flag | Flag variables still use 0/1 |

### Suppression Rates by Data Type

| Data Element | Typical Suppression Rate |
|--------------|-------------------------|
| Institution-level earnings | 5-15% |
| Field-of-study earnings | 40-60% |
| Disaggregated earnings (by income) | 30-50% |
| Small institution data | 20-40% |
| Small program data | 50-80% |

### Implications of Suppression

1. **Selection bias** - Institutions with data are systematically different
2. **Missing small programs** - Many programs have no earnings data
3. **Limited disaggregation** - Subgroup analysis often impossible
4. **Incomparability** - Can't rank if many are suppressed

## Selection Bias Sources

### Title IV Coverage Bias

The fundamental selection issue:

| Bias Source | Direction | Magnitude |
|-------------|-----------|-----------|
| Title IV only | Overrepresents lower-income | High at selective schools |
| FAFSA completion | Overrepresents engaged students | Moderate |
| Federal loan take-up | Varies by institution | Variable |

### Working Population Bias

Earnings only measured for those working:

| Bias Source | Direction | Magnitude |
|-------------|-----------|-----------|
| Excludes grad students | Overstates earnings for fields with high grad attendance | High for pre-med, pre-law |
| Excludes unemployed | Overstates earnings | Moderate |
| Excludes self-employed | Understates for entrepreneurial fields | High for arts, business |
| Excludes those abroad | Unknown | Low |

### Completers vs Non-Completers

| Group | Representation Issue |
|-------|---------------------|
| Completers | Generally good representation |
| Non-completers | May have left system entirely |
| Transfer students | Tracked, but complex |

## Known Data Errata

### Cohort Alignment Issues (2022-2023)

Entry-cohort earnings calculations were misaligned in some releases:
- Affected: `merged_2018_19` and `merged_2019_20` files
- Impact: Earnings measured for wrong cohort years
- Status: Check official errata document

### Historical Changes

| Period | Issue |
|--------|-------|
| Pre-2015 | Limited variables, different definitions |
| 2015 launch | Major expansion of variables |
| 2019-2020 | Repayment rate definition changes |
| 2020-2023 | Pandemic effects on repayment |

## Data Lag

### Built-in Lag Structure

| Metric | Data Age When Released |
|--------|----------------------|
| 6-year earnings | Reflects students from 7+ years ago |
| 10-year earnings | Reflects students from 11+ years ago |
| Completion rates | 6-8 years after entry |
| Repayment rates | Varies by metric |

### Implications of Lag

1. **Curriculum changes** - Current programs may differ from cohort experience
2. **Labor market shifts** - Demand may have changed
3. **Institutional changes** - Leadership, resources may differ
4. **Policy changes** - Aid, regulations may have changed

### When Lag Matters Most

| Situation | Lag Impact |
|-----------|------------|
| Fast-changing fields (tech) | High - data outdated |
| Stable fields (nursing) | Lower - consistent over time |
| New programs | No data yet |
| Major institutional change | Historical data not representative |

## Pandemic Effects (2020-2023)

### Repayment Data

| Effect | Impact |
|--------|--------|
| Payment pause | $0 payments counted as "on track" |
| No defaults | CDR artificially low |
| IDR expansion | Changed repayment patterns |

### Enrollment Data

| Effect | Impact |
|--------|--------|
| Enrollment drops | Smaller cohorts |
| Changed enrollment patterns | Different student composition |
| Online shift | May affect outcomes |

### Earnings Data

| Effect | Impact |
|--------|--------|
| Labor market disruption | 2020 earnings affected |
| Industry-specific effects | Hospitality, healthcare different |
| Geographic variation | Different regional impacts |

**Recommendation:** Use pre-pandemic cohorts for trend analysis; note pandemic effects explicitly.

## Comparability Issues

### What Cannot Be Compared

| Comparison | Problem |
|------------|---------|
| Scorecard vs IPEDS completion | Different populations |
| Scorecard vs BLS wages | Different measurement |
| Scorecard vs Census income | Different populations, definitions |
| Scorecard vs LinkedIn data | Different selection |
| Cross-country comparisons | No international data |

### What Can Be Compared (Carefully)

| Comparison | Conditions |
|------------|------------|
| Same institution over time | Note cohort changes |
| Similar institutions | Similar type, coverage rates |
| Same field across institutions | Same credential level |
| Subgroups within institution | If both not suppressed |

### Factors Affecting Comparability

| Factor | Issue |
|--------|-------|
| Title IV coverage rate | Different populations |
| Program mix | Different fields = different outcomes |
| Student body composition | Demographics affect outcomes |
| Regional labor market | Geography matters |
| Selectivity | Input quality differs |

## Measurement Issues

### Earnings Measurement

| Issue | Impact |
|-------|--------|
| W-2 only | Self-employment excluded |
| Point-in-time | Doesn't capture trajectory |
| Gross earnings | Taxes, benefits not considered |
| Cost of living | Not adjusted for location |

### Debt Measurement

| Issue | Impact |
|-------|--------|
| Federal only | Private loans excluded |
| Cumulative debt | Doesn't reflect repayment |
| Median | Distribution may be bimodal |
| No interest | Principal only |

### Completion Measurement

| Issue | Impact |
|-------|--------|
| Time-bound | Late completers missed |
| Any credential | Doesn't distinguish degree types |
| Transfer tracking | Complex at institutional level |

## Data Quality Indicators

### Variables to Check

| Check | Variables |
|-------|-----------|
| Sample size | `COUNT_WNE_P6`, `NUM4_PUB` |
| Suppression | `*_SUPP` flags |
| Coverage | Compare to IPEDS enrollment |
| Completeness | NULL counts by variable |

### Red Flags

| Indicator | Concern |
|-----------|---------|
| > 30% suppression in analysis | Selection bias likely |
| Very small counts | Noisy estimates |
| Large year-over-year changes | Data quality or real change? |
| Implausible values | Data errors |

## Recommended Quality Checks

### Before Analysis

```python
import polars as pl

# Check missing/suppression rates (null is primary indicator in Portal parquet)
missing_rate = df.filter(
    pl.col("md_earn_wne_p6").is_null()
).height / df.height

print(f"Missing/suppressed rate: {missing_rate:.1%}")

# Check sample sizes (for valid data only)
with_data = df.filter(pl.col("count_wne_p6").is_not_null())
small_samples = with_data.filter(pl.col("count_wne_p6") < 100)
print(f"Small samples: {small_samples.height}")

# Check for implausible values (filter valid values first)
valid_earnings = df.filter(
    pl.col("md_earn_wne_p6").is_not_null() &
    (pl.col("md_earn_wne_p6") > 0)
)
suspicious = valid_earnings.filter(
    (pl.col("md_earn_wne_p6") < 10000) |
    (pl.col("md_earn_wne_p6") > 500000)
)
print(f"Suspicious values: {suspicious.height}")
```

### During Analysis

1. **Report suppression rates** for each analysis
2. **Note sample sizes** especially for subgroups
3. **Flag small cells** in disaggregated analysis
4. **Document exclusions** and their impact

### Reporting Results

```
Standard caveat template:

"This analysis uses College Scorecard data with the following 
limitations: (1) Only Title IV aid recipients are included, 
representing approximately X% of students at these institutions; 
(2) Earnings data excludes self-employed and non-working individuals; 
(3) X% of [institutions/programs] had suppressed earnings data 
due to privacy thresholds; (4) Earnings reflect students who 
entered approximately Y years ago and may not reflect current 
conditions."
```

## Summary of Key Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Title IV only | Systematic selection bias | Note coverage, compare similar |
| Suppression | Missing small programs/schools | Report suppression rates |
| Data lag | Outdated information | Note cohort years |
| W-2 only | Missing self-employment | Acknowledge in interpretation |
| Federal debt only | Understates total borrowing | Note private loans excluded |
| Working only | Excludes non-workers | Note who is excluded |
| Pandemic effects | 2020-2023 data unusual | Use pre-pandemic for trends |
