# Education Data Portal: Practical Learnings

This document consolidates lessons learned from hands-on experience with the Urban Institute Education Data Portal. Use this to avoid common pitfalls and improve data retrieval efficiency.

---

## Table of Contents

1. [Mirror System](#mirror-system)
2. [Variable Name Discrepancies](#variable-name-discrepancies)
3. [Data Availability & Lag Times](#data-availability--lag-times)
4. [Endpoint-Specific Gotchas](#endpoint-specific-gotchas)
5. [Portal Integer Encoding Gotchas](#portal-integer-encoding-gotchas)
6. [Data Structure Patterns](#data-structure-patterns)
7. [Validation Patterns](#validation-patterns)

---

## Mirror System

**As of February 2026**, all data fetching uses the mirror-first approach (mirrors configured in `mirrors.yaml`). No REST API calls are used for data retrieval. Mirrors are tried in priority order; each mirror defines its own URL template, file format, and discovery mechanism.

### Mirror-Specific Learnings

| Mirror | Learning | Impact | Date |
|--------|----------|--------|------|
| `huggingface` | Complete coverage of all data levels (school-districts, schools, college-university) | Primary mirror for all datasets; urban_csv serves as fallback | 2026-02 |
| Mirrors with `lazy_csv` strategy | Default `infer_schema_length` may mistype columns | Use `infer_schema_length=10000` for reliable type inference | 2026-02 |
| Mirrors with `lazy_csv` strategy | Large files (500MB+) require lazy loading | Always use `pl.scan_csv()` with filters, never `pl.read_csv()` | 2026-02 |

**Note:** Mirror coverage should be verified via each mirror's discovery mechanism (see `mirrors.yaml`) rather than assumed. Coverage changes over time as new datasets are mirrored.

---

## Variable Name Discrepancies

### CRITICAL: Documentation vs. API Variable Names

The skill documentation and the actual API often use **different variable names**. Always verify with a test query.

| Documented Name | Actual API Name | Endpoint |
|-----------------|-----------------|----------|
| `inst_level` | `institution_level` | IPEDS Directory |
| `applicants_total` | `number_applied` | IPEDS Admissions |
| `admissions_total` | `number_admitted` | IPEDS Admissions |
| `admit_rate` | (not provided - calculate manually) | IPEDS Admissions |
| `enrollment_undergrad` | `enrollment_undergrad_fte` or needs separate endpoint | IPEDS |
| `efug` | `est_fte` | IPEDS Fall Enrollment |
| `enrollment_ft_ug` | `enrollment_fall` | IPEDS Fall Enrollment |
| `grad_rate_6yr` | `completion_rate_150pct` (scale: 0-1, not 0-100) | IPEDS Graduation Rates |

### Best Practice: Always Fetch Sample First

Before building a full data pipeline, fetch a single page and inspect columns:

```python
# Test query to see actual column names
response = requests.get(
    "https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2023/"
)
data = response.json()
print("Columns:", list(data['results'][0].keys()))
```

---

## Data Availability & Lag Times

### IPEDS Data Lag by Survey Component

| Survey Component | Typical Lag | As of Jan 2026 |
|------------------|-------------|----------------|
| **Directory** | ~1 year | 2023 available |
| **Admissions-Enrollment** | ~2 years | 2022 available (not 2023) |
| **Fall Enrollment** | ~2-3 years | 2021 available (not 2022-2023) |
| **Completions** | ~2 years | Varies |
| **Finance** | ~4+ years | **2017 is latest** (not 2018-2025) |
| **Graduation Rates** | ~2-3 years | 2021 available |

### CRITICAL: IPEDS Finance Data Cutoff

**As of Jan 2026, IPEDS Finance data is only available through 2017.**

This affects:
- Endowment values (`endowment_end`)
- Revenue and expense data
- Any financial ratios or calculations

**Workaround options:**
1. Forward-fill 2017 values with documented caveat
2. Limit analysis to 2012-2017
3. Use alternative data sources (NCCS 990 data for private institutions)

**If forward-filling:** Add indicator column and document prominently:
```python
# Add forward-fill indicator
df = df.with_columns([
    pl.when(pl.col('year') > 2017).then(pl.lit(True))
      .otherwise(pl.lit(False)).alias('finance_forward_filled')
])
```

### Pre-Flight Check for Year Availability

Always verify what years are actually available before promising a year range:

```python
# --- Check year availability ---
endpoint_base = "/college-university/ipeds/admissions-enrollment"
years_to_check = [2019, 2020, 2021, 2022, 2023]

availability = {}
for year in years_to_check:
    url = f"https://educationdata.urban.org/api/v1{endpoint_base}/{year}/"
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        data = response.json()
        availability[year] = data.get("count", 0)
    else:
        availability[year] = 0
    print(f"  {year}: {availability[year]:,} records")

print(f"\nAvailability: {availability}")
# Example output: {2019: 6033, 2020: 5967, 2021: 5943, 2022: 8686, 2023: 0}
```

### Endpoint Existence Check

Some endpoints that "should" exist based on documentation may return 404:

```python
# These DON'T exist (as of Jan 2026):
# /college-university/ipeds/enrollment-headcount/  <- 404
# /college-university/ipeds/enrollment/           <- 404
# /college-university/ipeds/12-month-enrollment/  <- 404

# These DO exist:
# /college-university/ipeds/fall-enrollment/      <- works
# /college-university/ipeds/directory/            <- works
# /college-university/ipeds/admissions-enrollment/ <- works
```

---

## Endpoint-Specific Gotchas

### IPEDS Directory

**What it has:**
- `unitid` (institution ID)
- `institution_level` (1=less-than-2yr, 2=2yr, 4=4yr) — NOTE: not `inst_level`
- `degree_granting` (1=yes, 0=no)
- `opeid` (Title IV ID - presence indicates accreditation)
- `inst_control` (1=public, 2=private nonprofit, 3=private for-profit)
- `inst_size` (categorical 1-5, not actual enrollment)

**What it DOESN'T have:**
- Actual enrollment counts (need separate endpoint)
- Admission rates (need admissions-enrollment endpoint)

### IPEDS Admissions-Enrollment

**Critical: Data is disaggregated by sex**

The admissions data includes separate rows for:
- `sex=1` (Male)
- `sex=2` (Female)
- `sex=3` (Another gender)
- `sex=9` (Unknown)
- `sex=99` (Total) ← **Use this for institution-level totals**

**Always filter to sex=99 for totals:**

```python
# Wrong - includes duplicates per institution
df = pl.read_parquet("admissions.parquet")  # Has ~26K rows

# Correct - one row per institution-year
df_totals = df.filter(pl.col("sex") == 99)  # Has ~8K rows
```

**Variable names:**
- `number_applied` (not `applicants_total`)
- `number_admitted` (not `admissions_total`)
- `number_enrolled_total` (entering class size, NOT total enrollment)

**Admission rate must be calculated:**
```python
df = df.with_columns(
    (pl.col("number_admitted") / pl.col("number_applied") * 100).alias("admit_rate")
)
```

### IPEDS Fall Enrollment

**Only provides FTE (Full-Time Equivalent), not headcount**

Variables available:
- `est_fte` - Estimated FTE enrollment
- `rep_fte` - Reported FTE enrollment
- `level_of_study` - 1=Undergraduate, 2=Graduate

**To get undergraduate only:**
```python
# Filter in API call or in URL
endpoint = "/college-university/ipeds/fall-enrollment/2021/?level_of_study=1"
```

**Data lag is significant:** As of Jan 2026, data only available through 2021.

---

## Portal Integer Encoding Gotchas

The Education Data Portal uses integer codes for categorical variables. While generally consistent, several patterns can cause data quality issues if not handled properly.

### CRITICAL: Grade -1 is Pre-K, NOT Missing Data

**This is the most dangerous semantic trap in the Portal.**

In CCD enrollment data, the grade field uses `-1` to represent **Pre-Kindergarten**, NOT missing data. Standard missing-value filters will incorrectly remove all Pre-K enrollment:

```python
# WRONG - Silently discards all Pre-K enrollment!
df_clean = df.filter(pl.col("grade") >= 0)

# WRONG - Also discards Pre-K!
df_clean = df.filter(~pl.col("grade").is_in([-1, -2, -3]))

# CORRECT - Handle Pre-K explicitly
df_k12 = df.filter(pl.col("grade").is_between(0, 12))  # K-12 only
df_all = df.filter(pl.col("grade").is_between(-1, 12))  # Pre-K through 12
df_totals = df.filter(pl.col("grade") == 99)  # Totals across all grades
```

**CCD Grade Code Reference:**
| Code | Meaning |
|------|---------|
| -1 | Pre-Kindergarten (NOT missing!) |
| 0 | Kindergarten |
| 1-12 | Grades 1-12 |
| 15 | Ungraded |
| 99 | Total |
| 999 | Not specified |

### Disaggregated Data: Always Filter to Totals

When data is disaggregated by race or sex, each institution has **multiple rows**. Failing to filter to totals causes overcounting:

```python
# WRONG - Counts each institution 5-10 times!
df_admissions = pl.read_parquet("admissions.parquet")
total_applied = df_admissions["number_applied"].sum()  # Inflated by 5-10x

# CORRECT - Filter to totals first
df_totals = df_admissions.filter(pl.col("sex") == 99)
total_applied = df_totals["number_applied"].sum()  # Correct total
```

**Sex Code Reference:**
| Code | Meaning |
|------|---------|
| 1 | Male |
| 2 | Female |
| 3 | Another gender / Nonbinary |
| 9 | Unknown |
| **99** | **Total (use this for institution-level counts)** |

**Race Code Reference:**
| Code | Meaning |
|------|---------|
| 1 | White |
| 2 | Black |
| 3 | Hispanic |
| 4 | Asian |
| 5 | American Indian/Alaska Native |
| 6 | Native Hawaiian/Pacific Islander |
| 7 | Two or More Races |
| 8 | Nonresident alien (postsecondary) |
| 9 | Unknown |
| **99** | **Total (use this for institution-level counts)** |

### Missing Data: Source-Dependent Patterns

Different sources use different patterns for missing/suppressed data. Using the wrong pattern will fail silently:

| Pattern | Sources | Detection |
|---------|---------|-----------|
| `-1/-2/-3` coded values | CCD, CRDC, EDFacts, EADA, NHGIS | Check for negative integers |
| Native `null` values | Scorecard, MEPS, NACUBO | Check for nulls |
| **Both patterns** | IPEDS, FSA | Must check for BOTH |

**Comprehensive missing data filter:**

```python
# For sources that may have both patterns (IPEDS, FSA)
df_clean = df.filter(
    pl.col("value").is_not_null() &
    ~pl.col("value").is_in([-1, -2, -3])
)

# For null-only sources (Scorecard, MEPS, NACUBO)
df_clean = df.filter(pl.col("value").is_not_null())

# For coded-only sources (CCD, CRDC, EDFacts)
df_clean = df.filter(~pl.col("value").is_in([-1, -2, -3]))
```

### Validation: Check for Unexpected Code Values

After fetching data, validate that categorical codes are within expected ranges:

```python
# Validate race codes (should be 1-9 or 99)
race_values = df["race"].unique().to_list()
unexpected_race = [v for v in race_values if v not in [1,2,3,4,5,6,7,8,9,99] and v >= 0]
if unexpected_race:
    print(f"[WARN] Unexpected race codes: {unexpected_race}")

# Validate sex codes (should be 1-3, 9, or 99)
sex_values = df["sex"].unique().to_list()
unexpected_sex = [v for v in sex_values if v not in [1,2,3,9,99] and v >= 0]
if unexpected_sex:
    print(f"[WARN] Unexpected sex codes: {unexpected_sex}")

# Validate grade codes (should be -1 to 12, 15, 99, or 999)
grade_values = df["grade"].unique().to_list()
valid_grades = set(range(-1, 13)) | {15, 99, 999}
unexpected_grade = [v for v in grade_values if v not in valid_grades]
if unexpected_grade:
    print(f"[WARN] Unexpected grade codes: {unexpected_grade}")
```

---

## Data Structure Patterns

### Coded Missing Values

Standard across most endpoints:

| Code | Meaning | Action |
|------|---------|--------|
| `-1` | Missing/not reported | Filter before calculations |
| `-2` | Not applicable | Exclude from analysis |
| `-3` | Suppressed for privacy | Cannot recover; document |
| `null` | Genuinely missing | Handle per analysis needs |

### Institution Level Codes (IPEDS)

| Code | Meaning |
|------|---------|
| 1 | Less than 2-year |
| 2 | 2-year |
| 4 | 4-year |
| -1 | Missing |

**Note:** There is no code 3. This is a common source of confusion.

### Institution Control Codes (IPEDS)

| Code | Meaning |
|------|---------|
| 1 | Public |
| 2 | Private nonprofit |
| 3 | Private for-profit |

---

## Validation Patterns

### Post-Fetch Validation Checklist

```python
# --- Post-Fetch Validation ---
# Configure these before running:
#   df = <fetched DataFrame>
#   expected_years = [2020, 2021, 2022]
#   critical_cols = ["unitid", "instnm", "year"]
print("\n" + "=" * 60)
print("POST-FETCH VALIDATION")
print("=" * 60)

fetch_valid = True

# Row count
print(f"  Row count: {df.height:,}")

# Year coverage
years_found = sorted(df["year"].unique().to_list())
years_missing = [y for y in expected_years if y not in years_found]
print(f"  Years found:   {years_found}")
if years_missing:
    print(f"  [WARN] Years missing: {years_missing}")

# Column coverage
columns_missing = [c for c in critical_cols if c not in df.columns]
if columns_missing:
    print(f"  [FAIL] Missing columns: {columns_missing}")
    fetch_valid = False
else:
    print(f"  [PASS] All {len(critical_cols)} critical columns present")

# Missingness rates for critical columns
for col in critical_cols:
    if col in df.columns:
        null_pct = df[col].null_count() / df.height * 100
        if null_pct > 50:
            print(f"  [WARN] {col}: {null_pct:.2f}% null (high)")
        elif null_pct > 0:
            print(f"  [WARN] {col}: {null_pct:.2f}% null")

# Status determination
if columns_missing:
    status = "FAILED"
elif years_missing:
    status = "WARNING"
else:
    status = "PASSED"

print(f"\nPOST-FETCH VALIDATION: {status}")
print("=" * 60)

assert fetch_valid, "STOP: Post-fetch validation failed — missing critical columns"
```

### Join Validation

When joining IPEDS datasets, validate cardinality:

```python
# --- Join Validation ---
# Configure these before running:
#   left_df = <left DataFrame>
#   right_df = <right DataFrame>
#   join_keys = ["unitid", "year"]
#   expected_cardinality = "1:1"  # "1:1", "1:many", "many:1", "many:many"
print("\n" + "=" * 60)
print("JOIN VALIDATION")
print("=" * 60)

join_valid = True

# Pre-join counts
left_count = left_df.height
right_count = right_df.height
print(f"  Left rows:  {left_count:,}")
print(f"  Right rows: {right_count:,}")

# Execute join
result = left_df.join(right_df, on=join_keys, how="left")
result_count = result.height
print(f"  Result rows: {result_count:,}")

# Check cardinality
fan_out_ratio = result_count / left_count if left_count > 0 else 0
print(f"  Fan-out ratio: {fan_out_ratio:.2f}x")

if expected_cardinality == "1:1":
    is_valid = result_count == left_count
    if not is_valid:
        print(f"  [FAIL] Expected 1:1 but result rows ({result_count:,}) != left rows ({left_count:,})")
        join_valid = False
    else:
        print(f"  [PASS] 1:1 cardinality confirmed")
elif expected_cardinality == "1:many":
    is_valid = result_count >= left_count
    if not is_valid:
        print(f"  [FAIL] Expected 1:many but result rows < left rows")
        join_valid = False
    else:
        print(f"  [PASS] 1:many cardinality confirmed")
else:
    print(f"  [PASS] Cardinality {expected_cardinality} (not strictly validated)")

print(f"\nJOIN VALIDATION: {'PASSED' if join_valid else 'FAILED'}")
print("=" * 60)

assert join_valid, "STOP: Join validation failed — cardinality mismatch"
```

---

---

---

## CCD Schools/Districts Endpoints

### CRITICAL: Enrollment Disaggregator URL Pattern

**Rule: For CCD enrollment endpoints, the `grade` disaggregator is REQUIRED and must come FIRST in the URL path.**

| Pattern | Status | Example |
|---------|--------|---------|
| `/enrollment/{year}/grade-{value}/` | ✅ WORKS | `/enrollment/2022/grade-99/` |
| `/enrollment/{year}/grade-{value}/race/` | ✅ WORKS | `/enrollment/2022/grade-99/race/` |
| `/enrollment/{year}/grade-{value}/sex/` | ✅ WORKS | `/enrollment/2022/grade-99/sex/` |
| `/enrollment/{year}/grade-{value}/race/sex/` | ✅ WORKS | `/enrollment/2022/grade-99/race/sex/` |
| `/enrollment/{year}/race/` | ❌ HTTP 500 | Race without grade fails |
| `/enrollment/{year}/sex/` | ❌ HTTP 500 | Sex without grade fails |
| `/enrollment/{year}/race/grade-{value}/` | ❌ HTTP 500 | Wrong order fails |

This pattern applies to both:
- `/schools/ccd/enrollment/`
- `/school-districts/ccd/enrollment/`

Use `grade-99` to get totals across all grades.

### SAIPE Field Names

All SAIPE fields have the `est_` prefix (estimates):

| Documented | Actual API Field |
|------------|------------------|
| `population_5_17_poverty` | `est_population_5_17_poverty` |
| `population_5_17_poverty_pct` | `est_population_5_17_poverty_pct` |

### CCD Finance Field Names

Finance fields often include `_total` suffix:

| Documented | Actual API Field |
|------------|------------------|
| `exp_current_instruction` | `exp_current_instruction_total` |

**Finance data lag:** As of Jan 2026, latest available year is 2020 (not 2021).

---

## CRDC Endpoints

### CRITICAL: Disaggregation is REQUIRED in URL Path

CRDC endpoints require disaggregation levels in the URL path (not optional):

| Documented | Actual Working Endpoint |
|------------|------------------------|
| `/schools/crdc/suspensions/{year}/` | ❌ Returns 404 |
| `/schools/crdc/discipline/{year}/disability/sex/` | ✅ Works |
| `/schools/crdc/ap-enrollment/{year}/` | ❌ Returns 404 |
| `/schools/crdc/ap-ib-enrollment/{year}/race/sex/` | ✅ Works |

**Race disaggregation cannot be used standalone** - must combine with other dimensions like disability or sex.

### Working CRDC Endpoints (no disaggregation required)

These endpoints work without path disaggregation:
- `/schools/crdc/offerings/{year}/` - Course offerings data
- `/schools/crdc/directory/{year}/` - School directory

### CRDC Years Available

CRDC is biennial: 2011, 2013, 2015, 2017, 2020, 2021

---

## MEPS Endpoint

### Field Names

| Documented | Actual API Field |
|------------|------------------|
| `school_poverty` | `meps_poverty_pct` |

Also available: `meps_mod_poverty_pct`

---

## EDFacts Endpoint

### Years Available

- **Assessments:** 2009-2018, 2020 (2019 is MISSING)
- **Graduation Rates:** 2010-2020 (2019 IS available)

### Grade Path Segment Required

For assessments, grade must be in URL path as `grade-{N}`:
- ✅ Works: `/edfacts/assessments/2018/grade-4/`
- ❌ Fails (404): `/edfacts/assessments/2018/?grade=4`
- ❌ Fails (500): `/edfacts/assessments/2018/4/`

---

---

---

---

## College/University IPEDS Endpoints (Additional)

### Graduation Rates Field Names

| Documented | Actual API Field |
|------------|------------------|
| `grad_rate_150pct` | `completion_rate_150pct` |

**IMPORTANT: Graduation rate is on 0-1 scale, not 0-100**

The `completion_rate_150pct` variable is a proportion (0.45 = 45%), not a percentage. Multiply by 100 for display:

```python
df = df.with_columns([
    (pl.col('completion_rate_150pct') * 100).alias('grad_rate_6yr')
])
```

### Enrollment Endpoint Path Segments

Path segments like `/undergrad/` in the URL return HTTP 500. Use query parameters instead:

| Fails | Works |
|-------|-------|
| `/fall-enrollment/2021/undergrad/` | `/fall-enrollment/2021/?level_of_study=1` |

### Enrollment-Headcount vs Fall-Enrollment

The API has TWO enrollment endpoints that both return FTE data (not headcount despite the name):

| Endpoint | Returns |
|----------|---------|
| `/ipeds/fall-enrollment/` | FTE fields (`est_fte`, `rep_fte`, `credit_hours`) |
| `/ipeds/enrollment-headcount/` | Also FTE-style data |

Neither returns traditional headcount enrollment.

---

## Changelog

| Date | Update |
|------|--------|
| 2026-02-07 | Added: Portal Integer Encoding Gotchas section - grade=-1 semantic trap, race/sex code tables, source-dependent missing data patterns, validation code examples |
| 2026-01-31 | Added: IPEDS Finance data cutoff at 2017, `enrollment_fall` variable name, graduation rate 0-1 scale clarification (from postsecondary enrollment analysis) |
| 2026-01-31 | Major update: CCD enrollment disaggregator rules, CRDC endpoint corrections, SAIPE/MEPS field names, summary endpoint requirements, metadata API filters, pagination behavior |
| 2026-01-24 | Initial version based on initial postsecondary analysis |

---

## See Also

- `education-data-explorer` skill - For identifying endpoints and variables
- `education-data-query` skill - For downloading data from mirrors
- `education-data-context` skill - For understanding caveats and limitations
- `education-data-source-ipeds` skill - For IPEDS-specific guidance
