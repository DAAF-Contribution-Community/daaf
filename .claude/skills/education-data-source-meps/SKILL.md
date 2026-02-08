---
name: education-data-source-meps
description: Model Estimates of Poverty in Schools (MEPS) - Urban Institute's school-level poverty measure. Use when analyzing school poverty rates, comparing poverty across states, or when FRPL data is unreliable due to CEP/universal meals programs. MEPS provides consistent cross-state poverty measurement at 100% FPL.
metadata:
  audience: data-analysts
  domain: education-data
---

# Model Estimates of Poverty in Schools (MEPS)

School-level poverty measure from the Urban Institute that is **comparable across states and time**, unlike Free/Reduced-Price Lunch (FRPL) data.

> **CRITICAL: Portal Integer Encoding**
>
> The Education Data Portal returns MEPS data with **integer-encoded** categorical and identifier columns. This differs from some external documentation:
>
> | Column | Portal Type | Example Value | Notes |
> |--------|-------------|---------------|-------|
> | `fips` | Int64 | `6` | State FIPS as integer (California = 6) |
> | `ncessch` | Int64 | `10000200277` | 12-digit NCES school ID as integer |
> | `leaid` | Int64 | `100002` | 7-digit district ID as integer |
> | `gleaid` | Int64 | `100013` | Geographic LEA ID as integer |
> | `year` | Int64 | `2018` | Academic year (fall semester) |
>
> **Missing values:** Unlike CCD, MEPS uses **native nulls** rather than negative coded values (-1, -2, -3). While the codebook lists these codes, actual Portal data contains nulls for missing values.

## What is MEPS?

MEPS is a **modeled estimate** of the share of students from households with incomes at or below **100% of the Federal Poverty Level (FPL)**:

- **Purpose**: Provide consistent school poverty measurement across all US states
- **Key advantage**: Comparable across states (unlike FRPL which varies by state policy)
- **Data level**: School-level (individual schools)
- **Coverage**: 2006-2019 (MEPS 1.0), expanded in MEPS 2.0
- **Source**: Urban Institute, derived from CCD and SAIPE data
- **API endpoint**: `/api/v1/schools/meps/{year}/`

## Why MEPS Instead of FRPL?

| Issue | FRPL Problem | MEPS Solution |
|-------|--------------|---------------|
| **CEP schools** | All students counted as "free lunch" regardless of income | Uses modeled estimates independent of meal programs |
| **State variation** | Different states use different eligibility criteria | Standardized 100% FPL threshold nationwide |
| **Direct certification** | Varies by state program participation | Calibrated to Census SAIPE data |
| **Income threshold** | 130-185% FPL (varies) | Consistent 100% FPL |
| **Time consistency** | Policy changes affect comparability over time | Methodology consistent across years |

**Critical insight**: As of 2020, ~60% of schools participate in CEP or other universal meal programs, making FRPL increasingly unreliable as a poverty proxy.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `methodology.md` | How MEPS estimates are calculated | Understanding the model, research validation |
| `comparison-to-frpl.md` | Detailed FRPL vs MEPS comparison | Deciding which measure to use |
| `data-sources.md` | Input data (CCD, SAIPE, ISP) | Understanding data provenance |
| `variable-definitions.md` | MEPS variables and codes | Building API queries, interpreting results |
| `data-quality.md` | Limitations, uncertainty, appropriate uses | Research design, caveats |
| `api-usage.md` | API endpoints and query examples | Querying MEPS data |

## Decision Trees

### Should I use MEPS or FRPL?

```
What is your research goal?
├─ Compare poverty across states → Use MEPS
│   └─ FRPL varies by state policy, MEPS is standardized
├─ Track poverty over time (post-2010) → Use MEPS
│   └─ CEP adoption makes FRPL inconsistent
├─ Study CEP/universal meals impact → Use both
│   └─ Compare MEPS (true poverty) vs FRPL (program participation)
├─ Match historical research (pre-2010) → Consider FRPL
│   └─ MEPS only available 2006+, but FRPL was more reliable then
├─ Need 185% FPL threshold → Use FRPL with caveats
│   └─ MEPS only measures 100% FPL
└─ Federal funding formulas → Check formula requirements
    └─ Some formulas mandate FRPL; note limitations
```

### Which MEPS variable should I use?

```
Which estimate type?
├─ Standard analysis → `meps`
│   └─ Original modeled estimate
├─ High-poverty district adjustment → `meps_mod`
│   └─ Modified MEPS for districts where model underestimates
├─ Need confidence bounds → `meps_se`
│   └─ Standard error for uncertainty analysis
└─ Categorical analysis → Derive from `meps`
    └─ Create quartiles/quintiles as needed
```

### How do I access MEPS data?

```
Access method?
├─ API query → ./references/api-usage.md
├─ R package → `educationdata::get_education_data(level='schools', source='meps')`
├─ Stata package → `educationdata, level(schools) source(meps)`
├─ Bulk download → educationdata.urban.org CSV downloads
└─ Join with other data → Use `ncessch` as join key
```

## Quick Reference: MEPS Variables

> **API Implementation:** For URL construction patterns, pagination, and error handling, see the `education-data-query` skill. For comprehensive API learnings, see `agent_reference/EDUCATION_DATA_API_LEARNINGS.md`.

### CRITICAL: API Field Names

The actual API field names differ from some documentation:

| Documented Name | Actual API Field |
|-----------------|------------------|
| `meps` / `school_poverty` | `meps_poverty_pct` |
| `meps_mod` | `meps_mod_poverty_pct` |
| `meps_se` | `meps_poverty_se` |

### Variable Reference (Portal Integer Encoding)

All ID and categorical columns use **integer encoding** in Portal data:

| Variable | Description | Type | Range/Notes |
|----------|-------------|------|-------------|
| `ncessch` | NCES school ID (12-digit) | **Int64** | e.g., `10000200277` |
| `ncessch_num` | NCES school ID (numeric duplicate) | **Int64** | Same as ncessch |
| `year` | School year (fall) | **Int64** | 2009-2022 (actual data range) |
| `fips` | State FIPS code | **Int64** | 1-56 |
| `leaid` | District ID (7-digit) | **Int64** | e.g., `100002` |
| `gleaid` | Geographic LEA ID | **Int64** | e.g., `100013` |
| `meps_poverty_pct` | Estimated share in poverty (100% FPL) | Float64 | 0.0-60.5% (actual range) |
| `meps_mod_poverty_pct` | Modified MEPS estimate | Float64 | 0.0-100.0% |
| `meps_poverty_se` | Standard error of estimate | Float64 | 0.5-3.8 (typical range) |
| `meps_poverty_ptl` | National percentile (enrollment-weighted) | **Int64** | 1-100 |
| `meps_mod_poverty_ptl` | Modified percentile (enrollment-weighted) | **Int64** | 1-100 |

**Missing values:** Use null checks, not negative value filters:
```python
# Correct
valid_data = df.filter(pl.col("meps_poverty_pct").is_not_null())

# Wrong (MEPS doesn't use -1, -2, -3 coded values)
# df.filter(pl.col("meps_poverty_pct") >= 0)  # Unnecessary
```

## Data Access via Mirrors

MEPS data is fetched from mirrors, not via REST API. See `education-data-query` skill.

| Mirror | Path |
|--------|------|
| huggingface | `schools/meps/schools_meps.parquet` |
| urban_csv | `meps/schools_meps.csv` |

**Example Fetch**:
```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/meps/schools_meps.parquet"
df = pl.read_parquet(url)

# Filter locally
df = df.filter(
    (pl.col("fips") == 6) &  # California
    (pl.col("year") == 2018)
)
```

## Key Methodological Points

1. **Model-based**: MEPS uses a linear probability model, not direct counts
2. **Calibrated to SAIPE**: District totals align with Census poverty estimates
3. **School-specific**: Reflects enrolled students, not neighborhood demographics
4. **100% FPL threshold**: Lower than FRPL (185%) - captures deeper poverty
5. **Public schools only**: Does not cover private schools

## Common Use Cases

| Use Case | Recommended Approach |
|----------|---------------------|
| School poverty rankings | Use `meps`, note `meps_se` for close comparisons |
| State-level aggregation | Sum weighted by enrollment |
| Poverty-achievement gaps | Join MEPS with EDFacts assessments on `ncessch` |
| Resource allocation analysis | Join MEPS with CCD finance on `leaid` |
| CEP impact research | Compare MEPS vs FRPL trends over time |
| Title I targeting analysis | Use `meps` to identify high-poverty schools |

## Joining MEPS with Other Data

| Source | Join Key | Use Case |
|--------|----------|----------|
| CCD Directory | `ncessch`, `year` | Add school characteristics |
| CCD Enrollment | `ncessch`, `year` | Get enrollment for weighting |
| CRDC | `ncessch`, `year` | Discipline, AP courses + poverty |
| EDFacts | `ncessch`, `year` | Achievement + poverty analysis |
| SAIPE (district) | `leaid`, `year` | Validate against Census estimates |

## Limitations to Note

- **Years available**: 2009-2022 (actual Portal data range)
- **Public schools only**: No private school coverage
- **Modeled estimates**: Subject to estimation error (use `meps_poverty_se`)
- **100% FPL only**: Does not capture near-poverty (100-185% FPL)
- **Not real-time**: 2-3 year data lag typical

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Linear probability model | `./references/methodology.md` |
| SAIPE calibration | `./references/methodology.md` |
| Modified MEPS | `./references/methodology.md` |
| Validation evidence | `./references/methodology.md` |
| CEP impact on FRPL | `./references/comparison-to-frpl.md` |
| Direct certification | `./references/comparison-to-frpl.md` |
| State policy variation | `./references/comparison-to-frpl.md` |
| CCD data inputs | `./references/data-sources.md` |
| SAIPE data inputs | `./references/data-sources.md` |
| ISP data (MEPS 2.0) | `./references/data-sources.md` |
| Variable definitions | `./references/variable-definitions.md` |
| Poverty thresholds | `./references/variable-definitions.md` |
| Standard errors | `./references/data-quality.md` |
| Appropriate uses | `./references/data-quality.md` |
| Known limitations | `./references/data-quality.md` |
| API endpoints | `./references/api-usage.md` |
| Query examples | `./references/api-usage.md` |
| R/Stata packages | `./references/api-usage.md` |

## Cross-Reference to Related Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Discover all available endpoints | Finding other data to join with MEPS |
| `education-data-query` | Construct API queries | Building complex MEPS queries |
