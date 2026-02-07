# Subgroup Reporting

Understanding how EDFacts reports data by student subgroups, including special populations, race/ethnicity, and the implications of n-size requirements and suppression.

## Contents

- [Required Subgroups](#required-subgroups)
- [Race/Ethnicity Reporting](#raceethnicity-reporting)
- [Special Populations](#special-populations)
- [N-Size Requirements](#n-size-requirements)
- [Suppression Rules](#suppression-rules)
- [Subgroup Analysis Considerations](#subgroup-analysis-considerations)
- [Gap Analysis](#gap-analysis)
- [Intersectional Subgroups](#intersectional-subgroups)

## Required Subgroups

### ESSA Accountability Subgroups

Under ESSA, states must report assessment and graduation data for these subgroups:

| Category | Subgroups |
|----------|-----------|
| All students | Total student population |
| Race/Ethnicity | 7 racial/ethnic groups |
| Special populations | CWD, EL, economically disadvantaged |
| Additional populations | Homeless, foster care, migrant, military |

### Subgroup Codes in EDFacts

| Code | Subgroup | Description |
|------|----------|-------------|
| `ALL` | All students | Total population |
| `ECODIS` | Economically disadvantaged | FRPL or other poverty measure |
| `CWD` | Children with disabilities | IDEA-eligible with IEP |
| `LEP` | Limited English proficient | English learner students |
| `HOM` | Homeless | McKinney-Vento identified |
| `FCS` | Foster care | In foster care system |
| `MIG` | Migrant | Migrant education program |
| `MIL` | Military connected | Military family students |

## Race/Ethnicity Reporting

### Federal Race/Ethnicity Categories

EDFacts uses the federal OMB race/ethnicity categories:

| Code | Category | Definition |
|------|----------|------------|
| `HI` | Hispanic/Latino | Hispanic or Latino of any race |
| `AM` | American Indian/Alaska Native | Non-Hispanic AI/AN |
| `AS` | Asian | Non-Hispanic Asian |
| `HP` | Native Hawaiian/Pacific Islander | Non-Hispanic NH/PI |
| `BL` | Black | Non-Hispanic Black or African American |
| `WH` | White | Non-Hispanic White |
| `MR` | Two or more races | Non-Hispanic, multiple races |

### Reporting Rules

| Rule | Details |
|------|---------|
| Hispanic first | Students who are Hispanic/Latino are reported in HI regardless of race |
| Mutually exclusive | Each student in only one category |
| Non-Hispanic | All other categories are for non-Hispanic students |
| Two or more | Students selecting multiple races who are not Hispanic |

### Race/Ethnicity Suppression

Small racial groups experience high suppression:

| Group | Typical Suppression |
|-------|---------------------|
| White | Low (larger population) |
| Hispanic | Low to moderate |
| Black | Moderate |
| Asian | Moderate to high |
| American Indian | High |
| Pacific Islander | Very high |
| Two or more | High |

## Special Populations

### Students with Disabilities (CWD)

Students receiving special education services under IDEA:

| Characteristic | Details |
|----------------|---------|
| Definition | Students with IEP under IDEA Part B |
| Reporting | Disability status, not type |
| Assessment | Most take general assessment |
| Alternate assessment | Up to 1% on alternate assessment (ESSA cap) |

#### CWD Considerations

| Issue | Impact |
|-------|--------|
| Exit from services | Students may exit disability status |
| Accommodation effects | Testing conditions may differ |
| Alternate assessment | Different test, different standards |
| Extended time | May affect graduation timelines |

### English Learners (LEP/EL)

Students identified as limited English proficient:

| Characteristic | Details |
|----------------|---------|
| Definition | Students not yet English proficient |
| Identification | State-determined criteria |
| Exit criteria | Varies by state |
| Former EL | Some states track formerly EL students |

#### EL Considerations

| Issue | Impact |
|-------|--------|
| Reclassification | Exit from EL status affects trend data |
| Length of time EL | Newer ELs vs. long-term ELs differ |
| Home language | Diverse language backgrounds |
| Testing accommodations | May affect results |

### Economically Disadvantaged (ECODIS)

Students from low-income families:

| Characteristic | Details |
|----------------|---------|
| Traditional measure | Free or reduced-price lunch eligibility |
| Threshold | 130% (free) / 185% (reduced) of poverty |
| Alternative measures | Direct certification, CEP |

#### ECODIS Definition Changes

| Era | Definition Issues |
|-----|-------------------|
| Pre-CEP | FRPL forms = good proxy |
| CEP schools | 100% counted, inflating rates |
| Alternative measures | States using different definitions |

```python
# Caution: ECODIS definition varies
def flag_cep_schools(df):
    """Flag schools likely using CEP (Community Eligibility Provision)."""
    
    return df.with_columns(
        pl.when(pl.col("econ_disadvantaged_pct") >= 99)
        .then(pl.lit("likely_cep"))
        .when(pl.col("econ_disadvantaged_pct") >= 75)
        .then(pl.lit("possible_cep"))
        .otherwise(pl.lit("traditional"))
        .alias("frpl_status")
    )
```

### Homeless Students (HOM)

Students identified under McKinney-Vento Act:

| Living Situation | Included |
|------------------|----------|
| Shelters | Yes |
| Hotels/motels | Yes |
| Doubled-up | Yes (with relatives due to economic hardship) |
| Cars, parks | Yes |
| Awaiting foster care | Yes |

### Foster Care (FCS)

Students in the foster care system:

| Characteristic | Details |
|----------------|---------|
| Definition | Under state child welfare agency care |
| Point of contact | District must have foster care liaison |
| Educational stability | Law requires minimizing school changes |

### Migrant Students (MIG)

Students in migrant education program:

| Characteristic | Details |
|----------------|---------|
| Definition | Family moves for agricultural/fishing work |
| Eligibility | Within 36 months of qualifying move |
| Certificate of Eligibility | Required documentation |

### Military-Connected Students (MIL)

Students from military families:

| Characteristic | Details |
|----------------|---------|
| Definition | Parent/guardian is active duty military |
| Challenges | Frequent school changes |
| Impact Schools | Schools near military installations |

## N-Size Requirements

### What is N-Size?

The minimum number of students required to report data for a subgroup:

| Purpose | Description |
|---------|-------------|
| Privacy protection | Prevent identification of individuals |
| Statistical reliability | Ensure meaningful calculations |
| Reporting threshold | Minimum for accountability |

### N-Size Variation by State

States set their own n-size, typically ranging from 10 to 30+:

| N-Size | Characteristics |
|--------|-----------------|
| Low (10-15) | More subgroups reported, more noise |
| Medium (20-25) | Balance of visibility and reliability |
| High (30+) | More reliable, but many excluded |

### Impact of N-Size on Reporting

| Lower N-Size | Higher N-Size |
|--------------|---------------|
| More schools report subgroups | Fewer schools report subgroups |
| More volatile estimates | More stable estimates |
| Better visibility for small groups | Small groups often excluded |
| Higher privacy risk | Lower privacy risk |

### Checking State N-Size

```python
# N-size affects what you can analyze
def estimate_n_size_effect(df, subgroup_col, count_col):
    """Estimate how different n-sizes would affect reporting."""
    
    n_sizes = [10, 15, 20, 25, 30]
    
    results = []
    for n in n_sizes:
        pct_reportable = (df[count_col] >= n).sum() / len(df) * 100
        results.append({
            "n_size": n,
            "pct_reportable": pct_reportable
        })
    
    return results
```

## Suppression Rules

### Primary Suppression

Data suppressed when cell size is too small:

| Rule | Application |
|------|-------------|
| N-size threshold | Fewer than n students |
| Small percentage | 0% or 100% in small groups |
| Individual identification | Any value that could identify student |

### Complementary Suppression

Additional cells suppressed to prevent calculation:

| Scenario | Action |
|----------|--------|
| Only one cell suppressed | Suppress another cell |
| Total reported | Suppress to prevent back-calculation |
| Subgroup math | Ensure all students + subgroups don't reveal |

### Example: Complementary Suppression

```
School has 100 students
- White: 45 students (45%)
- Hispanic: 30 students (30%)
- Black: 22 students (22%)
- Asian: 3 students (suppressed - too small)

If only Asian suppressed, you could calculate: 100 - 45 - 30 - 22 = 3

Solution: Suppress at least one other category
```

### Suppression Impact Analysis

```python
def analyze_subgroup_suppression(df, subgroup_col, value_col):
    """Analyze suppression rates by subgroup."""
    
    analysis = (df
        .group_by(subgroup_col)
        .agg([
            pl.count().alias("total_records"),
            (pl.col(value_col) == -3).sum().alias("suppressed"),
            (pl.col(value_col) >= 0).sum().alias("valid")
        ])
        .with_columns([
            (pl.col("suppressed") / pl.col("total_records") * 100)
            .alias("pct_suppressed"),
            (pl.col("valid") / pl.col("total_records") * 100)
            .alias("pct_valid")
        ])
        .sort("pct_suppressed", descending=True)
    )
    
    return analysis
```

## Subgroup Analysis Considerations

### Selection Bias from Suppression

| Issue | Impact |
|-------|--------|
| Small schools excluded | Larger schools overrepresented |
| Small subgroups excluded | Majority groups overrepresented |
| Rural areas affected | Urban data more complete |

### Handling Missing Subgroup Data

| Approach | When to Use |
|----------|-------------|
| Aggregate to district | Need complete data |
| Pool across years | More observations |
| Document exclusions | Be transparent |
| Use multiple imputation | Advanced analysis |

### Example: Aggregating for Complete Subgroup Data

```python
def aggregate_for_subgroups(df, geo_level, subgroup_col, value_cols):
    """Aggregate to higher geographic level for complete subgroup data."""
    
    # District aggregation reduces suppression
    aggregated = (df
        .group_by([geo_level, subgroup_col])
        .agg([
            pl.col(col).sum().alias(col) for col in value_cols
            if "count" in col or "num" in col
        ])
    )
    
    # Recalculate percentages
    # ... add percentage calculation logic
    
    return aggregated
```

## Gap Analysis

### Calculating Achievement Gaps

```python
def calculate_gaps(df, reference_group, comparison_groups, value_col):
    """Calculate achievement gaps between subgroups."""
    
    # Get reference group value
    ref_value = (df
        .filter(pl.col("subgroup") == reference_group)
        .select(pl.col(value_col).mean())
        .item()
    )
    
    # Calculate gaps for each comparison group
    gaps = []
    for group in comparison_groups:
        comp_value = (df
            .filter(pl.col("subgroup") == group)
            .select(pl.col(value_col).mean())
            .item()
        )
        
        gaps.append({
            "subgroup": group,
            "value": comp_value,
            "gap_from_reference": comp_value - ref_value,
            "reference_group": reference_group
        })
    
    return gaps
```

### Standard Gap Calculations

| Gap Type | Calculation |
|----------|-------------|
| White-Black gap | White rate - Black rate |
| White-Hispanic gap | White rate - Hispanic rate |
| All-CWD gap | All students rate - CWD rate |
| All-EL gap | All students rate - EL rate |
| Non-ECODIS vs ECODIS | Non-disadvantaged - Disadvantaged |

### Interpreting Gaps

| Gap Direction | Meaning |
|---------------|---------|
| Positive gap | Reference group higher |
| Negative gap | Reference group lower |
| Gap = 0 | Groups equal |

### Trend in Gaps

```python
def gap_trend(df, group1, group2, value_col):
    """Calculate how gap has changed over time."""
    
    yearly_gaps = (df
        .group_by(["year", "subgroup"])
        .agg(pl.col(value_col).mean().alias("avg_value"))
        .pivot(
            index="year",
            on="subgroup",
            values="avg_value"
        )
        .with_columns(
            (pl.col(group1) - pl.col(group2)).alias("gap")
        )
        .select(["year", "gap"])
        .sort("year")
    )
    
    return yearly_gaps
```

## Intersectional Subgroups

### What Intersectional Means

Students who belong to multiple subgroups:

| Example | Groups |
|---------|--------|
| Black students with disabilities | Race + CWD |
| Hispanic English learners | Race + EL |
| Low-income students with disabilities | ECODIS + CWD |

### Reporting Challenges

| Challenge | Impact |
|-----------|--------|
| Very small cells | High suppression |
| Complex n-size rules | May not report intersections |
| Multiple jeopardy | Compounded disadvantages masked |

### Limited Intersectional Data

EDFacts generally reports single-dimension subgroups:
- Race OR disability status
- Not race AND disability together

For intersectional analysis, consider:
- CRDC data (has some intersections)
- State-level microdata (if accessible)
- Research datasets (restricted access)

## Best Practices for Subgroup Analysis

### Do

1. **Document suppression rates** by subgroup
2. **Consider aggregation** when suppression is high
3. **Report sample sizes** alongside outcomes
4. **Calculate gaps** with clear reference groups
5. **Note definition changes** (especially ECODIS)

### Don't

1. **Don't ignore suppression** - it biases results
2. **Don't compare suppressed to unsuppressed** - apples to oranges
3. **Don't assume ECODIS is consistent** - CEP changed things
4. **Don't ignore subgroup exits** - reclassification matters

### Example: Complete Subgroup Report

```python
def comprehensive_subgroup_report(df, year, state_fips, value_col):
    """Generate comprehensive subgroup analysis with quality metrics."""
    
    # Filter to state/year
    data = df.filter(
        (pl.col("year") == year) & 
        (pl.col("fips") == state_fips)
    )
    
    # Calculate metrics by subgroup
    report = (data
        .group_by("subgroup")
        .agg([
            # Outcome
            pl.col(value_col).mean().alias("avg_outcome"),
            
            # Quality metrics
            pl.count().alias("n_schools"),
            (pl.col(value_col) == -3).sum().alias("n_suppressed"),
            (pl.col(value_col) >= 0).sum().alias("n_valid"),
        ])
        .with_columns([
            # Suppression rate
            (pl.col("n_suppressed") / pl.col("n_schools") * 100)
            .alias("pct_suppressed"),
            
            # Valid rate
            (pl.col("n_valid") / pl.col("n_schools") * 100)
            .alias("pct_valid")
        ])
        .sort("avg_outcome", descending=True)
    )
    
    return report
```

## Subgroup Quick Reference

| Subgroup | Code | Definition | Common Issues |
|----------|------|------------|---------------|
| All | ALL | Total | Baseline |
| Econ Dis | ECODIS | Low-income | CEP inflation |
| CWD | CWD | Disabilities | High suppression |
| EL | LEP | English learners | Reclassification |
| Homeless | HOM | McKinney-Vento | Underidentification |
| Foster | FCS | Foster care | Small population |
| Migrant | MIG | Migrant program | Seasonal variation |
| Military | MIL | Military families | Geographic concentration |
| White | WH | Non-Hispanic White | Reference group |
| Black | BL | Non-Hispanic Black | Achievement gaps |
| Hispanic | HI | Hispanic/Latino | EL overlap |
| Asian | AS | Non-Hispanic Asian | Heterogeneity |
| Am Indian | AM | AI/AN | High suppression |
| Pacific Islander | HP | NH/PI | Very high suppression |
| Two+ Races | MR | Multiple races | Growing population |
