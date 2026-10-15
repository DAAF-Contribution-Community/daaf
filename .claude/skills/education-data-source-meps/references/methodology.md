# MEPS Methodology

How Model Estimates of Poverty in Schools (MEPS) are calculated, validated, and should be interpreted for research purposes.

## Overview of the Modeling Approach

MEPS 2.0 uses a **multilevel (mixed-effects) linear regression model** to estimate the share of students in each school from households with incomes at or below **100% of the Federal Poverty Level (FPL)**.

### Core Concept

The model leverages two key data sources:
1. **School-level data** from CCD (free-lunch and direct-certification counts, enrollment, grades served, charter and magnet status)
2. **District-level poverty** from Census SAIPE, adjusted by Urban to public school students (the model outcome)

MEPS 2.0 fits a multilevel (mixed-effects) linear regression of adjusted SAIPE district poverty on district-aggregated free-lunch (or direct-certification) shares, with state random intercepts and slopes and district covariates, then applies the parameters to school-level data (Gutierrez & Blagg 2025).

## The MEPS Model

### Model Specification

Gutierrez & Blagg (2025) specify the district-level model as (ASCII rendering of their equation):

```
PctPov_ds = b0 + b1*x_ds + b2*Z_ds + u0_s + u1_s*x_ds + e_ds
```

Where:
- **PctPov_ds**: adjusted SAIPE share of public school students with family incomes up to 100% FPL in geographic school district d, state s
- **x_ds**: district-aggregated free-lunch share (direct-certification share in the direct-certification model)
- **Z_ds**: district control covariates, group mean centered by state and year (enrollment-weighted shares of schools serving elementary or middle grades, offering prekindergarten, and charter or magnet schools; whether the district is a primary or secondary district)
- **u0_s, u1_s**: state-level random intercept and random slope on x_ds, with an unstructured covariance matrix
- **e_ds**: error term (robust standard errors)

### Key Methodological Features

1. **SAIPE as outcome, not a constraint**: Original MEPS is a model prediction; its district aggregates are not forced to equal SAIPE. Only Modified MEPS is adjusted so district aggregates match adjusted SAIPE (see below)

2. **Adjusted SAIPE**: For geographic districts enrolling 10,000 or more students, Urban subtracts ACS-based estimates of non-public school students in poverty from SAIPE's count

3. **Two models**: A free-lunch model and a direct-certification model (direct-certification data from 2015). A state enters a model in a year if at least 90 percent of districts have data for at least 90 percent of students

4. **Enrollment weighting**: School-level measures are aggregated to geographic districts weighting by school enrollment

## Model Training and Estimation

### Estimation Data

The district-level model is estimated in each available year on the states that meet the 90/90 data rule, so the estimating sample changes over time (Gutierrez & Blagg 2025, Table 1). Gaps in direct-certification data are filled with ISPs from FRAC's CEP database, and FRPL observations that Stanford's Longitudinal Imputed School Dataset (LISD) flags as erroneous are replaced with LISD values in states that still report FRPL.

### Estimation Process

1. **Estimate the district-level model** (free-lunch and/or direct-certification) for each year
2. **Apply the estimated parameters to school-level data** to predict school poverty. A school needs nonmissing values for every covariate; states absent from the estimating sample still receive predictions
3. **Choose the model per state** when a state has both: Urban uses, for the whole state, the prediction that most closely resembles adjusted SAIPE aggregated to the state level
4. **Standard errors** are created using Stata 16's `predict` command

## Modified MEPS (`meps_mod`)

### Why Modified MEPS Exists

Urban's bias analysis finds that differences from adjusted SAIPE are larger by district race and ethnicity than by the other district characteristics it examined (which are within about 2 percentage points on average). Districts with high shares of Black students tend to be underestimated and districts with high shares of Asian students overestimated. Modified MEPS 2.0 is created "in an effort to resolve bias, particularly around student race and ethnicity" (Gutierrez & Blagg 2025).

### Modified MEPS Calculation

Modified MEPS reallocates modeled poor students so each district matches adjusted SAIPE, preserving relative school differences, both up and down. Urban's example: in a district with two equally sized schools modeled at 8% and 14%, a target adjusted SAIPE average of 12% moves them to 9% and 15%. Results are floored at 0% and capped at 100% (fewer than 1 percent of schools are affected). Modified MEPS exists only where the geographic district has a SAIPE value that year.

### When to Use Modified MEPS

| Scenario | Recommendation |
|----------|---------------|
| Analyses that include districts with smaller student populations | Use original `meps_poverty_pct` (Urban's suggestion) |
| Analyses only of schools within large-enrollment districts (e.g., the largest 100 districts) | Consider `meps_mod_poverty_pct` (Urban's suggestion) |
| Title I targeting or other resource allocation | Neither. Not for allocating resources within a state or district (Urban). Use for cross-state and longitudinal research. |

## Validation Evidence

### Correlation with SAIPE

District correlations with adjusted SAIPE in 2022: 0.80 (free-lunch model), 0.79 (direct-cert model). Aggregated to the state level, original MEPS 2.0 is generally within 2 percentage points of adjusted SAIPE in 2022; Arizona, Colorado, DC, Montana, Nebraska, New Mexico, and Vermont differ by more (Gutierrez & Blagg 2025). Modified MEPS is excluded from this validity check because it is constructed to match SAIPE.

### Year-to-Year Stability

Original MEPS 2.0 values are correlated at least 0.94 from one year to the next (Gutierrez & Blagg 2025, Table 5).

Urban's published validation is the adjusted-SAIPE comparison and year-to-year stability above (Gutierrez & Blagg 2025); tax-record and face-validity checks are not reported there.

## Standard Errors (`meps_se`)

### Interpretation

The standard error (`meps_se`) quantifies estimation uncertainty:
- **68% confidence interval**: meps ± 1 × meps_se
- **95% confidence interval**: meps ± 1.96 × meps_se

### Factors Affecting Standard Errors (DAAF inference; Urban reports robust SEs from Stata 16 `predict`, not these factors)

Standard errors tend to be larger for:
- Smaller schools (less data for estimation)
- Schools in districts with unusual characteristics

### Using Standard Errors in Research

```python
import polars as pl

# Identify schools where estimates are precise (SE < 2 percentage points)
precise_schools = df.filter(pl.col("meps_poverty_se") < 2.0)

# Flag close comparisons between two schools
def compare_schools(pct_a: float, se_a: float, pct_b: float, se_b: float) -> str:
    diff = abs(pct_a - pct_b)
    se_combined = (se_a**2 + se_b**2)**0.5
    if diff < 1.96 * se_combined:
        return "Not statistically different"
    return "Statistically different"
```

```r
library(dplyr)

# Identify schools where estimates are precise (SE < 2 percentage points)
precise_schools <- df |> filter(meps_poverty_se < 2.0)

# Flag close comparisons between two schools
# pct_a/se_a and pct_b/se_b: estimates and standard errors for schools A and B
diff <- abs(pct_a - pct_b)
se_combined <- sqrt(se_a^2 + se_b^2)
comparison <- if (diff < 1.96 * se_combined) {
  "Not statistically different"
} else {
  "Statistically different"
}
```

## MEPS 2.0 Updates

### Key Improvements in MEPS 2.0 (Released 2025-12-11)

> **Current vintage:** Urban's MEPS 2.0 release covers school years 2009-10 through 2022-23 and states that updates will occur annually. The Portal's 2022 endpoint returned rows (count 94,941) and its 2023 endpoint returned an empty result (count 0), re-probed 2026-08-06. Treat this as the observed publication vintage; no fixed methodological lag is documented.

1. **Extended time coverage**: School years 2009-10 through 2022-23 (MEPS 1.0: 2013-14 to 2018-19, superseded)
2. **Fuller ISP use**: MEPS 1.0 used some ISP data; 2.0 uses all available ISPs for 2013-14 through 2022-23 to fill missing direct-certification data
3. **LISD replaces state-by-state fixes**: erroneous FRPL observations are replaced with Stanford LISD imputations
4. **Corrected specification**: MEPS 2.0 uses a multilevel (mixed-effects) regression and corrects two MEPS 1.0 errors (a state fixed-effects coding error and a variance-covariance specification error).
5. **Dropped covariates**: Title I program eligibility and EDGE neighborhood poverty were removed after they became unavailable in 2022-23

### ISP (Identified Student Percentage)

ISP: from FRAC's CEP database (state-posted ISPs, 2013-14 onward), used to fill missing direct-certification data. MEPS 1.0 used some; 2.0 uses all available. Identified students are those certified for free meals without an application (directly certified via SNAP, TANF, FDPIR or, where USDA-approved, Medicaid, plus homeless, migrant, runaway, Head Start and non-application foster children). ISP is not identical to CCD's direct-certification count. See `data-sources.md` for matching details.

## Technical Notes

### Sample Restrictions

MEPS estimates are generated for:
- **Public schools only** (no private schools)
- **Open, nonvirtual schools serving grades K–12** in the 50 states and DC, with data on free lunch or direct certification students
- **Schools with enrollment data** in CCD

### Missing Data Handling

- A school missing any model covariate gets no MEPS 2.0 prediction (it can still count toward its district's aggregate in the district-level model)
- Missing direct-certification data are filled with FRAC ISPs where matched, and erroneous FRPL observations with LISD imputations (see Estimation Data above)
- Urban predicts MEPS 2.0 for more than 96 percent of schools each year (Gutierrez & Blagg 2025)

### Replication

The MEPS methodology is documented in:
- Gutierrez, Emily, Kristin Blagg, and Matthew Chingos. 2022. *Model Estimates of Poverty in Schools: A New School-Level Measure of Economic Need.* Washington, DC: Urban Institute. (MEPS 1.0)
- Gutierrez, Emily, and Kristin Blagg. 2025. *Model Estimates of Poverty in Schools 2.0.* Washington, DC: Urban Institute. (MEPS 2.0)

## Methodological Limitations

1. **Model assumptions**: The model assumes the distribution of students across federal-poverty-level thresholds is relatively consistent across types of schools and districts; Urban traces the race and ethnicity bias to this assumption (Gutierrez & Blagg 2025, appendix B)
2. **Data quality**: Depends on accuracy of CCD and SAIPE inputs
3. **Changing estimation sample**: The model is re-estimated each year on the states with sufficient data, so the set of states changes over time
4. **Private schools**: Not covered by MEPS
5. **Within-district variation**: Model captures some but not all variation

## Summary

MEPS provides a **rigorous, validated, and comparable** school-level poverty measure by:
- Using a statistical model fit to adjusted Census SAIPE district poverty
- Accounting for FRPL inconsistencies across states and time
- Providing uncertainty estimates via standard errors
- Offering modified estimates whose district aggregates match adjusted SAIPE

For most research purposes, MEPS provides a superior measure of school poverty compared to raw FRPL data, especially for cross-state comparisons or analyses spanning the CEP era (2010+).
