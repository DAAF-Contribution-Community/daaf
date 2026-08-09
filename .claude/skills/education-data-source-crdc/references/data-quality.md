# CRDC Data Quality Issues

Understanding data quality limitations is essential for responsible analysis of CRDC data. This reference covers known issues, suppression rules, state variations, and recommendations for handling quality concerns.

## Contents

- [Overview of Quality Concerns](#overview-of-quality-concerns)
- [Self-Reported Data Issues](#self-reported-data-issues)
- [Suppression Rules](#suppression-rules)
- [Definition Variation](#definition-variation)
- [Underreporting Concerns](#underreporting-concerns)
- [State Variations](#state-variations)
- [COVID-19 Impact (2020-21)](#covid-19-impact-2020-21)
- [Year-to-Year Comparability](#year-to-year-comparability)
- [Data Quality Checks](#data-quality-checks)

---

## Overview of Quality Concerns

### Major Quality Limitations

| Issue | Severity | Impact |
|-------|----------|--------|
| **Self-reported** | High | No independent verification |
| **Definition variation** | High | Same term, different meanings |
| **Underreporting** | Moderate-High | Counts may be understated |
| **Suppression** | Moderate | Missing subgroup data |
| **COVID impact (2020-21)** | High | Anomalous year |
| **State variation** | Moderate | Cross-state comparison difficult |

### Quality Varies by Data Element

| Data Element | Quality Concern Level | Primary Issues |
|--------------|----------------------|----------------|
| Enrollment | Low | Generally reliable |
| Discipline | High | Definition variation, underreporting |
| Restraint/seclusion | Very High | Severe underreporting |
| Harassment | High | Reporting inconsistency |
| Course offerings | Low-Moderate | Generally reliable |
| Chronic absenteeism | Moderate | Definition, COVID impact |
| Staffing | Low-Moderate | FTE calculation varies |

---

## Identifier Typing Across Vintages (`crdc_id` / `leaid`)

CRDC identifiers must be treated as strings, but their **raw file dtype is not
uniform across mirror vintages** — a change to watch when reproducing older
analyses or joining across files.

- **The one genuine dtype flip (v0.24.0 → v0.26.1):** in the discipline files
  `schools_crdc_discipline_k12_2020` (and `_2021`), `crdc_id` / `leaid` changed
  from `Int64` to `String`. The 2020/2021 discipline id domain went **alphanumeric**,
  so these ids can no longer be represented as integers. This was the **only**
  genuine dtype change across the 26 old↔new parquet *pairs* the v2 drift battery
  compared (observed 2026-08-06; see `education-data-query/references/vintage-drift.md`).
  It does **not** mean the 2020 vintage is uniformly typed — see the per-file
  heterogeneity bullet below.
- **Per-file heterogeneity within the 2020 vintage (do not generalize to "all
  String"):** a 2026-08-07 per-file audit found id dtypes vary *across* 2020 CRDC
  files: `schools_crdc_school_characteristics` stores `crdc_id`/`ncessch`/`leaid`
  all as String; `discipline_k12_2020` has `ncessch` as Int64 (with `crdc_id`/`leaid`
  String); `enrollment_k12_2020` has `crdc_id` as Int64; `harass_bully_students_2020`
  has all three as Int64. There is no universal String contract, which is exactly
  why the general rule below (normalize on read) matters. Where these ids are String
  they are zero-padded **numeric** strings (e.g. `0100002`, FIPS 01), not alphanumeric
  — the letter-bearing pattern is CCD-`districts_ccd_finance`-specific.
- **Why it matters for joins:** a script written against the old vintage may have
  keyed these columns as integers. Against the v2 mirror the same columns are
  strings, so a naive join can silently produce zero matches. Cast **both sides to
  String** before joining discipline files, and do not assume `Int64` id storage
  for 2020/2021 discipline data.
- **General rule (unchanged):** always read `crdc_id`, `ncessch`, and `leaid` as
  String (`pl.Utf8` / `col_character()`) regardless of the file's declared dtype,
  and validate width/domain per file. See the SKILL.md "String Type Override
  Required" warning. Parquet preserves the stored type, so an old-vintage parquet
  read still yields `Int64` for these columns while the v2 parquet yields `String` —
  normalize explicitly rather than relying on the stored type.

---

## Self-Reported Data Issues

### The Fundamental Limitation

CRDC is **self-reported by schools and districts**:
- Schools enter their own data
- No independent data collection
- OCR does not verify most submissions

### Implications

```
School Data Entry
       ↓
   CRDC System
       ↓
   OCR Review
       ↓
   Public Release
       
⚠️ No step involves independent data collection
```

### What Could Go Wrong

| Issue | Example |
|-------|---------|
| **Misinterpretation** | Different understanding of "suspension" |
| **Data system limitations** | School system doesn't track variable |
| **Entry errors** | Typos, wrong field |
| **Intentional underreporting** | Schools minimize negative metrics |
| **Lack of documentation** | Records not maintained |

### OCR Verification

OCR does:
- Run automated validation checks
- Follow up on outliers
- Investigate complaints (uses CRDC data)
- Conduct compliance reviews (may discover discrepancies)

OCR does NOT:
- Independently verify all submissions
- Audit school records routinely
- Validate counts against student records

---

## Suppression Rules

### Why Suppression Exists

Small cell sizes are suppressed to protect student privacy:
- Avoid identifying individual students
- Comply with FERPA requirements
- Prevent stigmatization

### Suppression Thresholds

| Level | Typical Threshold |
|-------|-------------------|
| OCR direct suppression | Counts of 1-5 students |
| Education Data Portal | Values of 1-5 typically suppressed |

### Types of Suppression

| Type | Description |
|------|-------------|
| **Primary suppression** | Direct suppression of small cell |
| **Complementary suppression** | Suppression to prevent back-calculation |

### Suppression Identification

In Education Data Portal:
- `-3` typically indicates suppression

```python
import polars as pl

def analyze_suppression(df, variables, grouping='state'):
    """
    Analyze suppression rates for variables.
    """
    suppression_report = {}
    
    for var in variables:
        total = df.height
        suppressed = df.filter(pl.col(var) == -3).height
        
        suppression_report[var] = {
            'total_records': total,
            'suppressed': suppressed,
            'suppression_rate': suppressed / total * 100
        }
        
        if suppression_report[var]['suppression_rate'] > 20:
            print(f"⚠️ WARNING: {var} has {suppression_report[var]['suppression_rate']:.1f}% suppression")
    
    return suppression_report
```

```r
library(dplyr)

# Analyze suppression rates for variables.
suppression_report <- list()

for (var in variables) {
    total <- nrow(df)
    suppressed <- df |> filter(.data[[var]] == -3) |> nrow()

    suppression_rate <- suppressed / total * 100

    suppression_report[[var]] <- list(
        total_records = total,
        suppressed = suppressed,
        suppression_rate = suppression_rate
    )

    if (suppression_rate > 20) {
        cat(sprintf("WARNING: %s has %.1f%% suppression\n", var, suppression_rate))
    }
}

suppression_report
```

### Impact on Analysis

| Analysis Type | Impact of Suppression |
|---------------|----------------------|
| National totals | Minimal (large counts) |
| State totals | Low-moderate |
| District analysis | Moderate |
| School analysis | High (especially small schools) |
| Subgroup analysis | Very high (small subgroups) |

### Handling Suppression

**DO NOT**:
- Replace suppressed values with 0
- Impute without documenting
- Ignore suppression in analysis

**DO**:
- Report suppression rates
- Use aggregate levels when suppression is high
- Document limitations
- Consider alternative approaches (range bounds)

---

## Definition Variation

### The Core Problem

CRDC provides definitions, but **districts interpret them differently**:

| Term | Potential Variations |
|------|---------------------|
| "Suspension" | Length thresholds vary |
| "Referral to law enforcement" | What counts as referral |
| "Restraint" | Physical escort included? |
| "Chronic absenteeism" | State definitions differ |
| "In-school suspension" | Lunch detention included? |

### Discipline Definition Examples

#### Suspension Length
- **District A**: Any removal from class >30 minutes = ISS
- **District B**: Only full-day removals = ISS
- **District C**: Uses "timeout" instead, doesn't count

#### Referral to Law Enforcement
- **District A**: Any contact with SRO = referral
- **District B**: Only formal referrals = referral
- **District C**: Informal conversations not counted

### Impact on Cross-District Comparison

```
⚠️ CAUTION: Direct comparison of discipline rates 
   across districts may reflect definition differences,
   not actual behavioral or policy differences.
```

### Mitigation Strategies

1. **Within-district comparisons** - Compare subgroups within same district
2. **Relative measures** - Use disparity ratios rather than absolute rates
3. **State-level analysis** - State definitions more consistent within state
4. **Time series within same unit** - Track changes over time in same school

---

## Underreporting Concerns

### Evidence of Underreporting

Research has identified systematic underreporting in several CRDC categories:

| Category | Evidence |
|----------|----------|
| **Discipline** | State administrative data often shows higher counts |
| **Restraint/seclusion** | Known severe underreporting nationwide |
| **Harassment** | Reporting dependent on school culture |
| **Arrests** | Coordination with law enforcement varies |

### Why Underreporting Occurs

| Reason | Mechanism |
|--------|-----------|
| **Documentation gaps** | Incidents not recorded |
| **Definition interpretation** | Narrow interpretation of terms |
| **Incentives** | Schools want to appear safe |
| **Data system limitations** | Systems don't track variables |
| **Staff training** | Incomplete understanding |
| **Resource constraints** | Burden of documentation |

### Restraint and Seclusion: A Case Study

Restraint and seclusion data is known to be severely underreported:

- Many schools report **zero** incidents
- Investigative reporting has found undocumented incidents
- OCR investigations reveal unreported incidents
- State data often shows higher counts

### Analytical Implications

```python
def interpret_zero_counts(df, variable):
    """
    Interpret zero counts with appropriate skepticism.
    
    Zero could mean:
    - No incidents occurred
    - Incidents occurred but weren't documented
    - Definition interpretation excludes incidents
    - Data system doesn't capture this variable
    """
    zero_count = df.filter(pl.col(variable) == 0).height
    total = df.height
    zero_pct = zero_count / total * 100
    
    interpretation = {
        'zero_schools': zero_count,
        'zero_percentage': zero_pct,
        'confidence': 'LOW' if zero_pct > 50 else 'MODERATE',
        'note': 'High zero rate may indicate underreporting'
    }
    
    return interpretation
```

```r
library(dplyr)

# Interpret zero counts with appropriate skepticism.
#
# Zero could mean:
# - No incidents occurred
# - Incidents occurred but weren't documented
# - Definition interpretation excludes incidents
# - Data system doesn't capture this variable
zero_count <- df |> filter(.data[[variable]] == 0) |> nrow()
total <- nrow(df)
zero_pct <- zero_count / total * 100

interpretation <- list(
    zero_schools = zero_count,
    zero_percentage = zero_pct,
    confidence = ifelse(zero_pct > 50, "LOW", "MODERATE"),
    note = "High zero rate may indicate underreporting"
)

interpretation
```

---

## State Variations

### Sources of State Variation

| Source | Example |
|--------|---------|
| **State laws** | Corporal punishment legal in some states |
| **State definitions** | Chronic absenteeism thresholds |
| **State reporting systems** | Some states pre-populate CRDC |
| **Policy environment** | Discipline reform policies |
| **Training** | State-provided CRDC training |

### States with Notable Differences

| Issue | States Affected |
|-------|-----------------|
| **Corporal punishment** | Legal in ~20 states, mostly South |
| **SRO policies** | Major variation in SRO presence |
| **Discipline reform** | Some states mandate data collection |
| **Restraint/seclusion** | State laws vary significantly |

### Cross-State Comparison Guidance

**Appropriate**:
- Broad regional comparisons
- National trends over time
- Within-state analysis

**Caution Required**:
- Direct state-to-state comparisons
- Ranking states by rates
- Attributing differences to policy without context

---

## COVID-19 Impact (2020-21)

### Why 2020-21 Is Anomalous

The 2020-21 school year was heavily impacted by COVID-19:

| Factor | Impact on Data |
|--------|----------------|
| **School closures** | Less opportunity for incidents |
| **Remote learning** | Discipline in virtual settings unclear |
| **Attendance tracking** | "Chronic absenteeism" redefined |
| **Course offerings** | Some courses not offered |
| **Staffing disruptions** | High turnover, vacancies |

### Specific Data Impacts

| Data Element | Expected Impact |
|--------------|-----------------|
| Discipline (all types) | Artificially low |
| Restraint/seclusion | Very low (less in-person) |
| Chronic absenteeism | Definition changed; not comparable |
| Course enrollment | Disrupted offerings |
| Harassment | Mixed (less in-person, more cyber) |

### COVID-Specific Data Elements (2020-21)

CRDC added temporary COVID-related variables:
- Amount of remote instruction
- Percentage of students receiving remote instruction
- Internet and device access

### Recommendations for 2020-21 Data

```
✅ DO:
- Analyze 2020-21 separately from other years
- Note COVID context in any findings
- Use for cross-sectional analysis only
- Compare within 2020-21 (relative disparities)

❌ DO NOT:
- Include in time series with pre-pandemic years
- Draw conclusions about trends including 2020-21
- Compare absolute values to other years
- Assume patterns are representative
```

### Example Disclaimer

> "Analysis of 2020-21 CRDC data should be interpreted with caution due to 
> significant disruptions from the COVID-19 pandemic. Many schools operated 
> remotely or in hybrid modes, fundamentally altering the context for 
> discipline, attendance, and course enrollment data. Direct comparison 
> to other CRDC years is not appropriate."

---

## Year-to-Year Comparability

### Factors Affecting Comparability

| Factor | Impact |
|--------|--------|
| **Coverage verification** | Collection scope must be checked by cycle; 2013-14 is an official universe collection |
| **Variable changes** | Variables added, removed, redefined |
| **Definition changes** | Same variable, different definition |
| **Form changes** | Collection instrument updates |
| **Policy changes** | National/state policy shifts |

### Safe Time Series Periods

| Period | Comparability | Notes |
|--------|---------------|-------|
| 2011 vs. 2013 | Limited | Verify 2011-12 coverage separately; 2013-14 is universe |
| 2013-2015-2017 | Potentially usable | Universe collections; still harmonize definitions and variables |
| Including 2020-21 | Poor | COVID impact |
| 2021-22 onward | Good | Post-pandemic baseline |

### Variable Availability by Year

| Variable | 2011 | 2013 | 2015 | 2017 | 2020 | 2021 |
|----------|------|------|------|------|------|------|
| Basic discipline | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Restraint/seclusion | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Chronic absenteeism | - | - | ✓ | ✓ | ✓ | ✓ |
| Preschool discipline | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Computer science | - | - | - | ✓ | ✓ | ✓ |
| Suspension instances | - | - | - | - | ✓ | ✓ |
| School days missed | - | - | - | - | ✓ | ✓ |

---

## Data Quality Checks

### Recommended Quality Checks

```python
import polars as pl

def crdc_quality_checks(df, year):
    """
    Run standard quality checks on CRDC data.

    Note: Portal uses integer codes for race/sex disaggregation.
    Total rows have race=99, sex=99.
    """
    checks = {}

    # 1. Check for implausible values (negative counts other than coded missing)
    checks['unexpected_negative'] = df.filter(
        (pl.col('enrollment_crdc') < -3)  # Below coded missing range
    ).height

    # 2. Get total rows only (race=99 means all races combined)
    totals = df.filter(pl.col('race') == 99)

    # 3. Check discipline > enrollment for totals
    checks['discipline_exceeds_enrollment'] = totals.filter(
        pl.col('students_susp_out_sch_single') > pl.col('enrollment_crdc')
    ).height

    # 4. Check suppression rates by race (use integer codes)
    # race=2 is Black, race=3 is Hispanic, race=1 is White
    for race_code, race_name in [(2, 'black'), (3, 'hispanic'), (1, 'white')]:
        race_df = df.filter(pl.col('race') == race_code)
        if race_df.height > 0:
            suppressed = race_df.filter(
                pl.col('students_susp_out_sch_single') == -3
            ).height
            checks[f'oss_{race_name}_suppression_rate'] = suppressed / race_df.height * 100

    # 5. Check zero inflation (using totals)
    if totals.height > 0:
        checks['zero_discipline_schools'] = totals.filter(
            pl.col('students_susp_out_sch_single') == 0
        ).height / totals.height * 100

    # 6. Year-specific checks
    if year == 2020 or year == 2021:
        checks['covid_year_warning'] = True
        checks['note'] = 'COVID-19 impacted year - interpret with caution'

    return checks
```

```r
library(dplyr)

# Run standard quality checks on CRDC data.
#
# Note: Portal uses integer codes for race/sex disaggregation.
# Total rows have race=99, sex=99.
checks <- list()

# 1. Check for implausible values (negative counts other than coded missing)
checks$unexpected_negative <- df |>
    filter(enrollment_crdc < -3) |>
    nrow()

# 2. Get total rows only (race=99 means all races combined)
totals <- df |> filter(race == 99)

# 3. Check discipline > enrollment for totals
checks$discipline_exceeds_enrollment <- totals |>
    filter(students_susp_out_sch_single > enrollment_crdc) |>
    nrow()

# 4. Check suppression rates by race (use integer codes)
# race=2 is Black, race=3 is Hispanic, race=1 is White
race_codes <- list(c(2, "black"), c(3, "hispanic"), c(1, "white"))
for (rc in race_codes) {
    race_code <- as.integer(rc[1])
    race_name <- rc[2]
    race_df <- df |> filter(race == race_code)
    if (nrow(race_df) > 0) {
        suppressed <- race_df |>
            filter(students_susp_out_sch_single == -3) |>
            nrow()
        checks[[paste0("oss_", race_name, "_suppression_rate")]] <-
            suppressed / nrow(race_df) * 100
    }
}

# 5. Check zero inflation (using totals)
if (nrow(totals) > 0) {
    checks$zero_discipline_schools <- totals |>
        filter(students_susp_out_sch_single == 0) |>
        nrow() / nrow(totals) * 100
}

# 6. Year-specific checks
if (year == 2020 || year == 2021) {
    checks$covid_year_warning <- TRUE
    checks$note <- "COVID-19 impacted year - interpret with caution"
}

checks
```

### Red Flags to Watch For

| Red Flag | Possible Issue |
|----------|----------------|
| Discipline > Enrollment | Data entry error |
| Sudden large changes | Definition or policy change |
| All zeros for category | Underreporting or system issue |
| Subgroup sum ≠ total | Calculation or reporting error |
| Very low restraint counts | Likely underreporting |
| High suppression rates | Small populations, privacy limits |

### Documentation Checklist

When analyzing CRDC data, document:

- [ ] Collection year and coverage type
- [ ] Variables used and their definitions
- [ ] Suppression rates for key variables
- [ ] Known limitations for analysis type
- [ ] COVID impact (if using 2020-21)
- [ ] State-specific considerations
- [ ] Comparison year appropriateness

---

## Recommendations Summary

### For All Analyses

1. **Document limitations** - Always note data quality concerns
2. **Check suppression** - Assess impact before analysis
3. **Use rates** - Normalize by enrollment
4. **Compare within units** - Same district, same school over time
5. **Verify definitions** - Check the live codebook for your year (use `get_codebook_url()` from `fetch-patterns.md`)

### For Discipline Analysis

1. **Expect underreporting** - Counts are likely low
2. **Use disparity ratios** - Compare groups within same context
3. **Control for school type** - Elementary vs. high school differ
4. **Note policy context** - Zero tolerance, reform policies

### For Time Series

1. **Use verified universe collections** - 2013-14 is officially universe; verify each cycle and harmonize definitions
2. **Exclude or flag 2020-21** - COVID anomaly
3. **Check variable consistency** - Same definition across years
4. **Same schools if possible** - Panel approach

### For Subgroup Analysis

1. **Check suppression first** - Small groups often suppressed
2. **Aggregate when needed** - Combine categories if necessary
3. **Use relative measures** - Disparity ratios more stable
4. **Document sample sizes** - Report N for subgroups
