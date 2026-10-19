# IPEDS Data Quality and Known Issues

Understanding data quality considerations, missing data, and analytical pitfalls.

## Contents

- [Data Quality Overview](#data-quality-overview)
- [Missing Data Codes](#missing-data-codes)
- [Imputation](#imputation)
- [Response Rates](#response-rates)
- [Known Data Quality Issues](#known-data-quality-issues)
- [Sector Comparison Warnings](#sector-comparison-warnings)
- [Historical Data Issues](#historical-data-issues)
- [Validation Checks](#validation-checks)
- [Data Quality Flags](#data-quality-flags)

## Data Quality Overview

### IPEDS Strengths

| Strength | Description |
|----------|-------------|
| High response rate | Greater than 99 percent for each component in the Spring 2018 collection; about 89 to over 99 percent for Title IV institutions since web collection began (NCES Handbook of Survey Methods) |
| Consistent definitions | Standardized across institutions |
| Longitudinal coverage | Many surveys since 1980s |
| Public access | Free, well-documented |
| Regular updates | Annual collection |

### IPEDS Limitations

| Limitation | Description |
|------------|-------------|
| Institutional-level only | No student-level data |
| Title IV focus | Non-Title IV institutions report only voluntarily; their coverage is partial |
| Cohort definitions | GR excludes many students |
| Accounting differences | GASB vs FASB |
| Lag time | 1-2 year delay for most data |
| Voluntary items | Some data elements optional |

## Missing Data Codes

> **CRITICAL: Portal Integer Encoding**
>
> The Education Data Portal uses **integer codes** for missing/special values. These differ from raw NCES file conventions.

IPEDS uses specific codes for missing or suppressed data:

### Standard Missing Data Codes (Portal Integer Encoding)

| Code | Meaning | Use |
|------|---------|-----|
| `-1` | Missing/not reported | State/institution did not report; value unknown |
| `-2` | Not applicable | Item doesn't apply to this institution |
| `-3` | Suppressed | Suppressed for privacy protection |
| `null`/`None` | Null value | No data present |

### Handling Missing Data

```python
import polars as pl

# Filter out missing/not applicable
valid_data = df.filter(
    pl.col("variable") > 0  # Excludes negative codes and nulls
)

# Or explicitly handle each code
df = df.with_columns(
    pl.when(pl.col("variable") < 0)
    .then(None)
    .otherwise(pl.col("variable"))
    .alias("variable_clean")
)
```

```r
library(dplyr)

# Filter out missing/not applicable
valid_data <- df |> filter(variable > 0)

# Or explicitly handle each code
df <- df |>
  mutate(variable_clean = if_else(variable < 0, NA_real_, variable))
```

### Privacy Suppression (-3)

Small cell counts are suppressed to protect privacy:
- Threshold not documented here; check the Portal codebook for -3 usage
- Common in demographic breakdowns
- More common at smaller institutions

```python
# Check for suppression
suppressed = df.filter(pl.col("variable") == -3)
print(f"Suppressed cells: {suppressed.height}")
```

```r
# Check for suppression
suppressed <- df |> filter(variable == -3)
cat("Suppressed cells:", nrow(suppressed), "\n")
```

### Not Applicable (-2)

Code `-2` is used when item doesn't apply:
- Graduation rates for non-degree institutions
- Graduate data for undergrad-only institutions
- Distance education for institutions without DE programs

## Imputation

### IPEDS Imputation Process

For non-respondents, IPEDS performs a single imputation after all editing is complete, using a nearest-neighbor approach (earlier years used cold-deck imputation, updated by ratio methods, and hot-deck imputation). NCES cautions that imputed values are intended for national totals, not as an accurate portrayal of an individual institution; check response-status and item imputation flags.

### Imputation Flags

IPEDS provides imputation flags in detailed data files:

| Flag | Meaning |
|------|---------|
| R | Reported by institution |
| P | Reported, adjusted by IPEDS |
| I | Imputed |
| D | Derived |

```python
# Check imputation rate
imputed = df.filter(pl.col("variable_flag") == "I")
imputation_rate = imputed.height / df.height * 100
print(f"Imputation rate: {imputation_rate:.1f}%")
```

```r
# Check imputation rate
imputed <- df |> filter(variable_flag == "I")
imputation_rate <- nrow(imputed) / nrow(df) * 100
cat(sprintf("Imputation rate: %.1f%%\n", imputation_rate))
```

### Best Practices

1. **Check imputation rates** for key variables
2. **Note high imputation** in analysis limitations
3. **Exclude highly imputed data** for sensitive analyses
4. **Use imputation flags** when available

## Response Rates

### Overall Response

IPEDS unit response rates are very high (greater than 99 percent for each component in the Spring 2018 collection; about 89 to over 99 percent for Title IV institutions since web collection began; NCES Handbook of Survey Methods) because reporting is mandatory for Title IV participants and NCES follows up extensively. Nonrespondents are imputed.

### Component-Specific Response

| Component | Response Considerations |
|-----------|------------------------|
| IC | Required; high response |
| EF, E12 | High response |
| C | High response |
| SFA | High response |
| GR | Some small cohorts suppressed |
| F | Some delayed reporting |
| HR | High response |
| AL | Annual from 2014-15 (biennial before) |

### Unit Non-Response

Entire institution doesn't respond:
- Rare (<1%)
- Often new or closing institutions
- Entire record imputed or excluded

### Item Non-Response

Individual items missing:
- More common than unit non-response
- Varies by item complexity
- Imputed using methods above

## Known Data Quality Issues

### Issue 1: Enrollment Count Timing

| Problem | Different census dates across institutions |
|---------|------------------------------------------|
| Impact | Point-in-time comparisons affected |
| Mitigation | Use 12-month enrollment for year-round schools |

### Issue 2: First-Time Student Classification

| Problem | Dual enrollment students may be misclassified |
|---------|----------------------------------------------|
| Impact | Affects GR cohorts, first-time enrollment |
| Mitigation | Note in analysis; may not be fixable |

### Issue 3: Branch Campus Reporting

| Problem | Inconsistent branch vs main campus reporting |
|---------|---------------------------------------------|
| Impact | Some data at campus level, some at system |
| Mitigation | Aggregate to OPEID6 level; check patterns |

### Issue 4: Online Program Growth

| Problem | DE definition changes, COVID disruption |
|---------|----------------------------------------|
| Impact | Pre-2020 to post-2020 not comparable |
| Mitigation | Note structural break; analyze separately |

### Issue 5: For-Profit Sector Volatility

| Problem | High closure/change rate in for-profit sector |
|---------|----------------------------------------------|
| Impact | Longitudinal analysis challenging |
| Mitigation | Track closures; note sample changes |

### Issue 6: Race/Ethnicity Unknown

| Problem | High "unknown" rates at some institutions |
|---------|------------------------------------------|
| Impact | Demographic analysis unreliable |
| Mitigation | Check unknown rates; exclude high-unknown institutions |

### Issue 7: Finance Data Comparability

| Problem | GASB vs FASB; passthrough transactions |
|---------|---------------------------------------|
| Impact | Cross-sector analysis problematic |
| Mitigation | See `finance-data.md`; Delta Cost Project (AIR) harmonized data cover 1986-87 through 2011-12 only |

### Issue 8: Graduation Rate Cohort

| Problem | FTFT cohort not representative |
|---------|--------------------------------|
| Impact | See `graduation-rates.md` |
| Mitigation | Use Outcome Measures; note limitations |

## Sector Comparison Warnings

### Public vs Private Comparisons

| Data Type | Comparability | Issues |
|-----------|---------------|--------|
| Enrollment | Moderate | Different student populations |
| Completions | Moderate | Different program mixes |
| Finance | Low | GASB vs FASB |
| Graduation rates | Low | Different populations |
| Net price | Moderate | Different aid structures |

### 4-Year vs 2-Year Comparisons

| Data Type | Comparability | Issues |
|-----------|---------------|--------|
| Enrollment | Moderate | Different missions |
| Completions | Moderate | Different award levels |
| Graduation rates | Very low | Transfer mission ignored |
| Finance | Low | Different cost structures |

### Selective vs Open-Access

| Data Type | Comparability | Issues |
|-----------|---------------|--------|
| Graduation rates | Very low | Input vs outcome |
| Enrollment demographics | Low | Selection effects |
| Financial aid | Moderate | Different student needs |

### Best Practice: Peer Group Analysis

Always compare within peer groups:
- Same sector (public/private NP/private FP)
- Same level (4-year/2-year/less-than-2-year)
- Similar selectivity (Carnegie classification)
- Similar size
- Same geographic region (if relevant)

```python
# Define peer group
peers = df.filter(
    (pl.col("inst_control") == 1) &  # Public
    (pl.col("institution_level") == 4) &    # 4-year (Portal code is 4, not 1)
    (pl.col("carnegie_basic").is_in(peer_carnegies)) &
    (pl.col("enrollment_size").is_between(5000, 15000))
)
```

```r
library(dplyr)

# Define peer group
peers <- df |>
  filter(
    inst_control == 1,           # Public
    institution_level == 4,      # 4-year (Portal code is 4, not 1)
    carnegie_basic %in% peer_carnegies,
    enrollment_size >= 5000, enrollment_size <= 15000
  )
```

## Historical Data Issues

### Survey Changes Over Time

| Year | Change | Impact |
|------|--------|--------|
| 1986 | IPEDS begins | Start of consistent data |
| 1997 | FASB finance | Private finance changes |
| 2002-04 | GASB finance | Public finance changes |
| 2008-09 to 2011-12 | New race/ethnicity categories phased in (required 2010-11 for EF/HR, 2011-12 for all components) | Two or more races and separate NHPI added; transition years mix schemes |
| 2008-09 to 2010-11 | Postbaccalaureate award levels restructured (phase-in from 2008-09; required 2010-11) | First-professional degree and certificate categories eliminated; doctor's split into research/scholarship, professional practice, other (Portal `award_level` 20/21 "until 2008", 22-24 "starting 2007") |
| 2012 | Distance education added | New data element |
| 2015 | Outcome Measures begins | New survey |
| 2020 | COVID impacts | Major disruption |

### Old-Scheme Race/Ethnicity (Before the 2008-09 to 2011-12 Phase-In)

Before adoption (EF/HR: 2010-11; other components: 2011-12):
- No "Two or more races" category
- "Asian" included Pacific Islander
- Different classification rules

```python
# Combining old and new race data
# Two+ races: phased in from 2008-09; required 2010-11 (EF/HR), 2011-12 (other components)
# Old scheme: Asian includes Pacific Islander. The year cutoff below is illustrative —
# during the 2008-09 to 2010-11 phase-in, check which scheme each institution reported.

if year < 2008:
    asian_combined = asian  # Includes Pacific Islander
else:
    asian_combined = asian + nhpi  # Separate in new data
```

```r
# Combining old and new race data
# Two+ races: phased in from 2008-09; required 2010-11 (EF/HR), 2011-12 (other components)
# Old scheme: Asian includes Pacific Islander. The year cutoff below is illustrative —
# during the 2008-09 to 2010-11 phase-in, check which scheme each institution reported.

asian_combined <- if (year < 2008) {
  asian  # Includes Pacific Islander
} else {
  asian + nhpi  # Separate in new data
}
```

### Finance Form Changes

Cannot directly compare:
- Pre-1997 private to post-1997 private
- Pre-2004 public to post-2004 public

Delta Cost Project (AIR) provides harmonized data for 1986-87 through 2011-12 only.

## Validation Checks

### Basic Validation

```python
def validate_ipeds_data(df, key_vars):
    """Basic IPEDS data validation."""
    issues = []
    
    # 1. Check for duplicate UNITIDs
    dups = df.group_by("unitid").count().filter(pl.col("count") > 1)
    if dups.height > 0:
        issues.append(f"Duplicate UNITIDs: {dups.height}")
    
    # 2. Check for missing critical fields
    for var in key_vars:
        missing = df.filter(pl.col(var).is_null()).height
        if missing > 0:
            issues.append(f"Missing {var}: {missing} rows")
    
    # 3. Check for implausible values
    # Portal stores grad rates as 0-1 proportions (not 0-100)
    # See education-data-context skill > Rate and Proportion Normalization
    if "completion_rate_150pct" in df.columns:
        bad_grad = df.filter(
            (pl.col("completion_rate_150pct") > 1.0) | (pl.col("completion_rate_150pct") < 0)
        )
        if bad_grad.height > 0:
            issues.append(f"Invalid grad rates: {bad_grad.height}")
    
    # 4. Check enrollment reasonableness
    if "enrollment" in df.columns:
        huge = df.filter(pl.col("enrollment") > 200000)
        if huge.height > 0:
            issues.append(f"Unusually large enrollments: {huge.height}")
    
    return issues
```

```r
library(dplyr)

# Basic IPEDS data validation
# 1. Check for duplicate UNITIDs
dups <- df |> count(unitid) |> filter(n > 1)
if (nrow(dups) > 0) cat("Duplicate UNITIDs:", nrow(dups), "\n")

# 2. Check for missing critical fields
key_vars <- c("unitid", "year", "enrollment")
for (v in key_vars) {
  n_missing <- sum(is.na(df[[v]]))
  if (n_missing > 0) cat("Missing", v, ":", n_missing, "rows\n")
}

# 3. Check for implausible values
# Portal stores grad rates as 0-1 proportions (not 0-100)
if ("completion_rate_150pct" %in% names(df)) {
  bad_grad <- df |> filter(completion_rate_150pct > 1.0 | completion_rate_150pct < 0)
  if (nrow(bad_grad) > 0) cat("Invalid grad rates:", nrow(bad_grad), "\n")
}

# 4. Check enrollment reasonableness
if ("enrollment" %in% names(df)) {
  huge <- df |> filter(enrollment > 200000)
  if (nrow(huge) > 0) cat("Unusually large enrollments:", nrow(huge), "\n")
}
```

### Consistency Checks

```python
def check_consistency(df):
    """Check internal consistency."""
    issues = []
    
    # Full-time + part-time should equal total
    if all(c in df.columns for c in ["ft_enrl", "pt_enrl", "total_enrl"]):
        inconsistent = df.filter(
            (pl.col("ft_enrl") + pl.col("pt_enrl") != pl.col("total_enrl")) &
            (pl.col("total_enrl") > 0)
        )
        if inconsistent.height > 0:
            issues.append(f"FT+PT != Total: {inconsistent.height}")
    
    # Race categories should sum to total
    race_cols = ["white", "black", "hispanic", "asian", "nhpi", 
                 "aian", "two_more", "unknown", "nonres"]
    if all(c in df.columns for c in race_cols + ["total"]):
        race_sum = sum(pl.col(c) for c in race_cols)
        inconsistent = df.filter(race_sum != pl.col("total"))
        if inconsistent.height > 0:
            issues.append(f"Race sum != Total: {inconsistent.height}")
    
    return issues
```

```r
library(dplyr)

# Check internal consistency
# Full-time + part-time should equal total
if (all(c("ft_enrl", "pt_enrl", "total_enrl") %in% names(df))) {
  inconsistent <- df |>
    filter(ft_enrl + pt_enrl != total_enrl, total_enrl > 0)
  if (nrow(inconsistent) > 0) cat("FT+PT != Total:", nrow(inconsistent), "\n")
}

# Race categories should sum to total
race_cols <- c("white", "black", "hispanic", "asian", "nhpi",
               "aian", "two_more", "unknown", "nonres")
if (all(c(race_cols, "total") %in% names(df))) {
  inconsistent <- df |>
    mutate(race_sum = rowSums(across(all_of(race_cols)))) |>
    filter(race_sum != total)
  if (nrow(inconsistent) > 0) cat("Race sum != Total:", nrow(inconsistent), "\n")
}
```

### Year-Over-Year Checks

```python
def check_yoy_changes(df, max_change=0.5):
    """Flag large year-over-year changes."""
    df = df.sort(["unitid", "year"])
    
    df = df.with_columns(
        (pl.col("enrollment") / pl.col("enrollment").shift(1) - 1)
        .over("unitid")
        .alias("yoy_change")
    )
    
    suspicious = df.filter(pl.col("yoy_change").abs() > max_change)
    return suspicious
```

```r
library(dplyr)

# Flag large year-over-year changes
max_change <- 0.5

df <- df |>
  arrange(unitid, year) |>
  group_by(unitid) |>
  mutate(yoy_change = enrollment / lag(enrollment) - 1) |>
  ungroup()

suspicious <- df |> filter(abs(yoy_change) > max_change)
```

## Data Quality Flags

### Institution Status Flags

| Portal Variable | Description | Check |
|-----------------|-------------|-------|
| `currently_active_ipeds` | Currently active | Should be 1 for analysis |
| `inst_category` | Institutional category (degree-granting level, codes 1-6) — not a status | Check for changes |
| `year_deleted` | Year deleted from IPEDS (closure, merger, or out of scope; -2 = not applicable) | Exclude deleted institutions (`year_deleted` > 0) |
| `inst_status` | Institution status | Active vs inactive |

> **Note:** NCES raw file documentation may use different variable names (e.g., `CYACTIVE`, `INSTCAT`, `DEATHYR`). The Portal uses the lowercase descriptive names shown above. Always verify against the actual data columns.

### Data Quality Flags

| Flag Type | Description |
|-----------|-------------|
| Imputation flags | Indicate imputed values |
| Revision flags | Indicate revised data |
| Status flags | Indicate reporting issues |

### Using Flags in Analysis

```python
import polars as pl

# Example: Quality-filtered analysis using Portal variable names
analysis_data = df.filter(
    (pl.col("currently_active_ipeds") == 1) &  # Active institutions
    ((pl.col("year_deleted").is_null()) | (pl.col("year_deleted") < 0)) &  # Not deleted (-2 = not applicable)
    (pl.col("enrollment") > 100)               # Minimum size (if applicable)
)

# Document filtering
print(f"Original: {df.height}")
print(f"Analysis sample: {analysis_data.height}")
print(f"Excluded: {df.height - analysis_data.height}")
```

```r
library(dplyr)

# Quality-filtered analysis using Portal variable names
analysis_data <- df |>
  filter(
    currently_active_ipeds == 1,   # Active institutions
    (is.na(year_deleted) | year_deleted < 0),  # Not deleted (-2 = not applicable)
    enrollment > 100               # Minimum size (if applicable)
  )

# Document filtering
cat("Original:", nrow(df), "\n")
cat("Analysis sample:", nrow(analysis_data), "\n")
cat("Excluded:", nrow(df) - nrow(analysis_data), "\n")
```

## Recommended Workflow

1. **Download data with flags** - Include imputation/status flags
2. **Check response rates** - Document non-response
3. **Validate basic quality** - Run validation checks
4. **Filter appropriately** - Remove problematic records
5. **Document decisions** - Note all exclusions
6. **Sensitivity analysis** - Test with/without exclusions
7. **Note limitations** - Include in write-up
