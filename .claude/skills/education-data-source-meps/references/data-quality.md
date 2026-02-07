# MEPS Data Quality and Appropriate Uses

Understanding the limitations, uncertainty, and appropriate applications of Model Estimates of Poverty in Schools.

## Key Data Quality Considerations

### MEPS is a Modeled Estimate

MEPS values are **statistical estimates**, not direct counts:

- Generated from a linear probability model
- Subject to estimation error
- Standard errors quantify uncertainty
- Individual school estimates less reliable than aggregates

**Implication**: Use standard errors for statistical inference; don't treat point estimates as ground truth.

### Estimation Uncertainty (`meps_se`)

The standard error indicates reliability:

| `meps_se` Range | Interpretation | Typical Context |
|-----------------|----------------|-----------------|
| < 0.02 | Very reliable | Large schools, abundant data |
| 0.02 - 0.05 | Reliable | Typical schools |
| 0.05 - 0.10 | Moderate uncertainty | Smaller schools, unusual characteristics |
| > 0.10 | High uncertainty | Small schools, missing predictors |

**Using standard errors:**
```python
# 95% confidence interval
lower = df['meps'] - 1.96 * df['meps_se']
upper = df['meps'] + 1.96 * df['meps_se']

# Flag unreliable estimates
df['reliable'] = df['meps_se'] < 0.05
```

## Known Limitations

### 1. Public Schools Only

MEPS covers **only public schools**:
- No private schools
- No religious schools
- No home schools
- Limited alternative school coverage

**Impact**: Cannot compare public vs private school poverty; national totals exclude private sector.

### 2. Time Coverage

| Version | Years Available | Notes |
|---------|-----------------|-------|
| MEPS 1.0 | 2006-2019 | Original release |
| MEPS 2.0 | Extended range | December 2025 release |

**Impact**: Cannot analyze poverty before 2006 or after available years with MEPS.

### 3. Data Lag

MEPS depends on CCD and SAIPE data, both of which have lag:
- CCD: ~1-2 years behind current year
- SAIPE: Released December for prior year
- MEPS: Additional processing time

**Impact**: Most recent year available is typically 2-3 years behind current date.

### 4. 100% FPL Only

MEPS measures **only students at or below 100% FPL**:
- Does not capture near-poverty (100-185% FPL)
- Lower threshold than FRPL
- Some economically disadvantaged students not counted

**Impact**: MEPS will show lower poverty rates than FRPL even when FRPL is reliable.

### 5. Model Assumptions

The linear probability model assumes:
- Relationships are approximately linear
- Coefficients are stable across schools and time
- Available predictors capture relevant variation

**Impact**: Estimates may be biased for schools with unusual characteristics not captured by the model.

### 6. High-Poverty District Bias

The original MEPS model **underestimates** poverty in very high-poverty districts:
- Use `meps_mod` for analyses focused on high-poverty contexts
- Original `meps` may undercount in districts >30% poverty

### 7. Small School Uncertainty

Smaller schools have larger estimation errors:
- Less information for the model
- Higher standard errors
- Consider combining small schools for analysis

## Appropriate Uses

### Strongly Appropriate

| Use Case | Why Appropriate |
|----------|-----------------|
| Cross-state poverty comparison | MEPS designed specifically for this |
| Time trends (2006-2019) | Consistent methodology |
| Poverty-achievement gap analysis | Better control than FRPL |
| Identifying high-poverty schools | More accurate than FRPL in CEP era |
| Research on school resources and poverty | Consistent measure |
| District-level aggregation | Calibrated to SAIPE |

### Appropriate with Caveats

| Use Case | Caveats |
|----------|---------|
| Individual school analysis | Use standard errors; acknowledge uncertainty |
| Small school analysis | High uncertainty; consider aggregation |
| Very high-poverty districts | Consider `meps_mod` instead |
| Year-over-year changes for single school | Changes may be within uncertainty |
| Near-poverty analysis | MEPS only captures 100% FPL |

### Not Appropriate

| Use Case | Why Not | Alternative |
|----------|---------|-------------|
| Private school poverty | Not covered | Use other measures |
| Before 2006 | No data | Use FRPL (with caveats) |
| Real-time monitoring | Data lag | Use local data |
| 185% FPL threshold | Different threshold | Use FRPL (with CEP adjustment) |
| Meal program planning | Wrong measure | Use FRPL/ISP |
| Compliance with FRPL-based formulas | May not satisfy requirements | Use FRPL |

## Statistical Considerations

### Comparing Schools

When comparing poverty between schools:

```python
def statistically_different(school_a, school_b, alpha=0.05):
    """Test if two schools have significantly different poverty rates."""
    diff = school_a['meps'] - school_b['meps']
    se_diff = (school_a['meps_se']**2 + school_b['meps_se']**2)**0.5
    z_score = abs(diff) / se_diff
    
    # Critical value for two-tailed test
    z_critical = 1.96 if alpha == 0.05 else 2.58  # 0.01
    
    return z_score > z_critical
```

### Aggregating to Higher Levels

For district or state aggregation, use enrollment-weighted averages:

```python
def aggregate_meps(df, groupby_col):
    """Enrollment-weighted aggregation with proper SE propagation."""
    grouped = df.groupby(groupby_col).apply(
        lambda x: pd.Series({
            'meps_weighted': (x['meps'] * x['enrollment']).sum() / x['enrollment'].sum(),
            'total_enrollment': x['enrollment'].sum(),
            # SE of weighted average (approximate)
            'meps_se_agg': ((x['meps_se']**2 * x['enrollment']**2).sum()**0.5 
                           / x['enrollment'].sum())
        })
    )
    return grouped
```

### Regression with MEPS

When using MEPS as a control variable:

```python
import statsmodels.api as sm

# Simple approach (ignores measurement error)
model = sm.OLS(y, sm.add_constant(df[['meps', 'other_vars']]))
results = model.fit()

# Better: Consider measurement error
# MEPS has known SE; consider errors-in-variables regression
# or sensitivity analysis varying MEPS within its CI
```

## Data Validation Checks

### Before Using MEPS Data

1. **Check for missing values**
```python
missing_pct = (df['meps'] < 0).mean()
print(f"Missing: {missing_pct:.1%}")
```

2. **Verify reasonable ranges**
```python
assert df['meps'].between(0, 1).all(), "MEPS out of range"
assert df['meps_se'].ge(0).all(), "Negative SE values"
```

3. **Check coverage**
```python
print(f"Schools covered: {df['ncessch'].nunique():,}")
print(f"States covered: {df['fips'].nunique()}")
print(f"Years covered: {df['year'].unique()}")
```

4. **Assess reliability distribution**
```python
df['meps_se'].describe()
print(f"Reliable estimates (SE<0.05): {(df['meps_se']<0.05).mean():.1%}")
```

## Reporting Recommendations

### In Research Papers

Always report:
1. MEPS version used
2. Years included
3. Sample restrictions applied
4. How standard errors were used
5. Acknowledgment that MEPS measures 100% FPL (not 185%)

Example text:
> "We measure school-level poverty using the Urban Institute's Model Estimates of Poverty in Schools (MEPS), which estimates the share of students from households with incomes at or below 100 percent of the federal poverty level. MEPS provides a consistent poverty measure across states and time, unlike FRPL data which is affected by policy variation and Community Eligibility Provision adoption (Gutierrez, Blagg, & Chingos, 2022)."

### In Policy Reports

Clarify:
1. Difference between MEPS and FRPL
2. Why MEPS is more comparable
3. Limitation that it measures 100% FPL
4. Data availability and recency

## Common Pitfalls

### 1. Ignoring Standard Errors

**Problem**: Treating MEPS point estimates as exact values
**Solution**: Always consider `meps_se` in comparisons and conclusions

### 2. Conflating with FRPL

**Problem**: Assuming MEPS and FRPL are interchangeable
**Solution**: Clearly distinguish; note different thresholds and methodologies

### 3. Single-School Conclusions

**Problem**: Making strong claims about individual schools
**Solution**: Use aggregations or acknowledge uncertainty

### 4. Outdated Data

**Problem**: Using MEPS for current policy without noting data lag
**Solution**: State the years covered; note lag

### 5. Ignoring Modified MEPS

**Problem**: Using original MEPS for high-poverty analysis
**Solution**: Use `meps_mod` when focusing on high-poverty districts

## Quality Assurance Checklist

Before publishing analysis using MEPS:

- [ ] Documented MEPS version and years used
- [ ] Excluded or flagged missing/suppressed values
- [ ] Considered standard errors in key findings
- [ ] Noted 100% FPL threshold (different from FRPL)
- [ ] Acknowledged limitations in discussion
- [ ] Used appropriate aggregation methods
- [ ] Cited Urban Institute methodology report

## Summary

MEPS is a **high-quality, research-grade** poverty measure when used appropriately:

| Strength | Limitation |
|----------|------------|
| Cross-state comparable | Model-based (not direct counts) |
| Time-consistent | 2-3 year data lag |
| Calibrated to Census | 100% FPL only (not 185%) |
| Accounts for CEP | Public schools only |
| Standard errors provided | Some uncertainty for small schools |

**Bottom line**: MEPS is the best available school-level poverty measure for research requiring cross-state or temporal comparability. Use standard errors, acknowledge limitations, and choose appropriate use cases.
