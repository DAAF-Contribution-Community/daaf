# survey Quickstart Reference

survey 4.5 on R 4.5.3 -- syntax and library guidance only.

---

## Contents

1. [Essential Setup](#essential-setup)
2. [Creating a Survey Design Object](#creating-a-survey-design-object)
3. [Basic Estimation](#basic-estimation)
4. [Confidence Intervals](#confidence-intervals)
5. [The Formula Interface](#the-formula-interface)
6. [Complete Workflow Example](#complete-workflow-example)
7. [Federal Survey Design Quick-Reference](#federal-survey-design-quick-reference)

---

## Essential Setup

```r
# --- Config ---
library(survey)

# Check version
cat("survey version:", as.character(packageVersion("survey")), "\n")
```

The survey package uses base R data.frames. Load data via `arrow::read_parquet()`
(DAAF convention) or base R `read.csv()`, then pass to `svydesign()`.

---

## Creating a Survey Design Object

All survey analysis starts with a design object that describes the sampling
structure. The design determines how standard errors are computed.

### Minimal Design (Weight Only)

```r
# Simple design with only weights (no strata, no clustering)
des <- svydesign(
  ids = ~1,              # no clustering
  weights = ~weight,
  data = df
)
```

### Stratified Design (No Clustering)

```r
des <- svydesign(
  ids = ~1,
  strata = ~region,
  weights = ~weight,
  data = df
)
```

### Clustered Design (No Stratification)

```r
des <- svydesign(
  ids = ~school_id,      # PSU / cluster variable
  weights = ~weight,
  data = df
)
```

### Full Complex Design (Stratified + Clustered)

```r
# Most federal surveys use this pattern
des <- svydesign(
  ids = ~psu_id,
  strata = ~stratum,
  weights = ~weight,
  data = df,
  nest = TRUE            # PSU IDs are nested within strata
)
```

### svydesign() Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ids` | Formula for PSU/cluster variable(s). Use `~1` for no clustering | Required |
| `strata` | Formula for stratification variable | `NULL` (no stratification) |
| `weights` | Formula for survey weight variable | `NULL` |
| `fpc` | Formula for finite population correction (population size or sampling fraction) | `NULL` |
| `data` | Data frame containing the survey data | Required |
| `nest` | If `TRUE`, PSU IDs are only unique within strata (not across the full dataset) | `FALSE` |

### The `nest = TRUE` Parameter

Most federal surveys (NHANES, BRFSS, etc.) use masked design variables where PSU
IDs are only meaningful within strata. For example, PSU "1" in stratum "A" is a
different unit than PSU "1" in stratum "B". Set `nest = TRUE` for these designs.

If PSU IDs are globally unique across all strata, `nest = FALSE` (default) is
correct.

### Finite Population Correction

When a substantial fraction of the population is sampled (> 5-10%), apply FPC:

```r
# FPC as population size per stratum
des <- svydesign(
  ids = ~psu_id,
  strata = ~stratum,
  weights = ~weight,
  fpc = ~pop_size,       # column with population size for each stratum
  data = df,
  nest = TRUE
)

# FPC as sampling fraction
des <- svydesign(
  ids = ~psu_id,
  strata = ~stratum,
  weights = ~weight,
  fpc = ~samp_fraction,  # column with fraction sampled (0-1)
  data = df,
  nest = TRUE
)
```

---

## Basic Estimation

Once the design object is created, estimation functions produce design-based
standard errors automatically.

### Population Mean

```r
# Mean of a continuous variable
result <- svymean(~income, design = des, na.rm = TRUE)
print(result)
# Output: mean and SE
```

### Population Total

```r
# Estimated population total
result <- svytotal(~enrollment, design = des, na.rm = TRUE)
print(result)
```

### Proportion

```r
# Proportions of a categorical variable -- wrap in factor()
result <- svymean(~factor(education_level), design = des, na.rm = TRUE)
print(result)
```

There is no separate `svyprop()` function -- proportions are estimated using
`svymean()` on a factor variable. Each level of the factor gets its own
proportion estimate with SE.

### Multiple Variables at Once

```r
# Estimate means of multiple variables in one call
result <- svymean(~income + age + bmi, design = des, na.rm = TRUE)
print(result)
```

### The `na.rm = TRUE` Argument

Always pass `na.rm = TRUE` for estimation functions. Without it, any `NA` in the
analysis variable causes the entire estimate to be `NA`. Document the effective
sample size after NA removal with an `# ASSUMES:` comment.

---

## Confidence Intervals

```r
# 95% confidence interval (default)
mn <- svymean(~income, design = des, na.rm = TRUE)
confint(mn)

# 99% confidence interval
confint(mn, level = 0.99)

# Works for all estimation functions
tot <- svytotal(~enrollment, design = des, na.rm = TRUE)
confint(tot)
```

### Extracting Components

```r
mn <- svymean(~income, design = des, na.rm = TRUE)

# Point estimate
coef(mn)

# Standard error
SE(mn)

# Variance-covariance matrix (useful for multi-variable estimates)
vcov(mn)

# Degrees of freedom
degf(des)
```

---

## The Formula Interface

The survey package uses R's formula interface (`~`) for specifying variables.
This is the same syntax used by `lm()` and `glm()`.

### Key Differences from Python svy

| R survey | Python svy | Notes |
|----------|-----------|-------|
| `svymean(~var, des)` | `sample.estimation.mean("var")` | R uses formula; Python uses string |
| `svydesign(ids = ~psu, strata = ~strat, weights = ~wt, data = df)` | `svy.Design(psu="psu", stratum="strat", wgt="wt")` + `svy.Sample(data=df, design=design)` | R combines in one call |
| `svyby(~var, ~group, des, svymean)` | `sample.estimation.mean("var", by="group")` | Domain estimation |
| `svyglm(y ~ x1 + x2, des)` | `sample.glm.fit(y="y", x=["x1", "x2"])` | R formula vs. Python lists |
| `subset(des, age >= 18)` | `where=pl.col("age") >= 18` on estimation/`glm.fit` (svy 0.19.0; estimation domain variance verified vs R `svyby`, `glm.fit` `where=` domain regression not yet cross-validated) | R preserves design structure |
| `factor(var)` in formula | `svy.Cat("var")` (required for string predictors in svy 0.19.0) | Categorical specification |

---

## Complete Workflow Example

```r
# --- Config ---
library(survey)
library(arrow)

# --- Load ---
data <- read_parquet("data/raw/nhanes_demo.parquet")
cat("Loaded", nrow(data), "rows,", ncol(data), "columns\n")

# --- Design ---
# INTENT: NHANES uses a complex multi-stage stratified cluster design
# REASONING: sdmvstra = pseudo-strata, sdmvpsu = pseudo-PSU,
#   wtmec2yr = 2-year MEC exam weight for exam-based analyses
# ASSUMES: Analysis population is the MEC-examined subsample
des <- svydesign(
  ids = ~sdmvpsu,
  strata = ~sdmvstra,
  weights = ~wtmec2yr,
  data = data,
  nest = TRUE
)

# --- Estimate ---
# Population mean BMI
mn_bmi <- svymean(~bmxbmi, design = des, na.rm = TRUE)
cat("Mean BMI:", round(coef(mn_bmi), 2), "\n")
cat("SE:", round(SE(mn_bmi), 4), "\n")
cat("95% CI:", round(confint(mn_bmi)[1], 2), "to",
    round(confint(mn_bmi)[2], 2), "\n")

# Proportions by gender
prop_gender <- svymean(~factor(riagendr), design = des, na.rm = TRUE)
cat("\nGender proportions:\n")
print(prop_gender)

# Domain estimation: mean BMI by gender
bmi_by_gender <- svyby(~bmxbmi, ~riagendr, design = des, svymean,
                        na.rm = TRUE)
cat("\nMean BMI by gender:\n")
print(bmi_by_gender)

# --- Validate ---
cat("\nSample size:", nrow(data), "\n")
cat("Design df:", degf(des), "\n")
stopifnot(nrow(data) > 0)
```

---

## Federal Survey Design Quick-Reference

Always verify against current survey documentation -- design variable names can
change across cycles.

| Survey | Strata | PSU | Weight(s) | Variance Method | nest= |
|--------|--------|-----|-----------|-----------------|-------|
| **NHANES** | `sdmvstra` | `sdmvpsu` | `wtmec2yr`, `wtint2yr`, subsample weights | Taylor | TRUE |
| **ACS PUMS** | N/A (use replicate weights) | N/A | `pwgtp` / `wgtp` | Bootstrap/SDR (80 reps) | N/A |
| **CPS ASEC** | N/A (use replicate weights) | N/A | `marsupwt` | Replicate: successive difference (SDR), 160 reps | N/A |
| **MEPS** | `varstr` | `varpsu` | `perwt__f` (year-specific) | Taylor | TRUE |
| **ECLS-K:2011** | Survey-specific | Survey-specific | Round-specific | Taylor or JKn | TRUE |
| **BRFSS** | `_ststr` | `_psu` | `_llcpwt` | Taylor | TRUE |
| **NHIS** | `pstrat` | `ppsu` | `wtfa_a` (adult), `wtfa_c` (child) | Taylor | TRUE |

NHIS design variables changed with the 2019 redesign: current files use
`pstrat`/`ppsu` with weights `wtfa_a` (adult) / `wtfa_c` (child); 2016-2018
used `pstrat`/`ppsu` with weight `wtfa_sa`; 2006-2015 used
`strat_p`/`psu_p`/`wtfa_sa`. For CPS ASEC replicate-weight setup, see
`replication.md`.

### NHANES Setup Pattern

```r
des <- svydesign(
  ids = ~sdmvpsu,
  strata = ~sdmvstra,
  weights = ~wtmec2yr,
  data = nhanes_data,
  nest = TRUE
)
```

### ACS PUMS Setup Pattern

```r
# ACS PUMS uses replicate weights -- see replication.md
des <- svrepdesign(
  weights = ~pwgtp,
  repweights = "pwgtp[0-9]+",
  type = "ACS",
  data = acs_data
)
```

### MEPS Setup Pattern

```r
des <- svydesign(
  ids = ~varpsu,
  strata = ~varstr,
  weights = ~perwt21f,
  data = meps_data,
  nest = TRUE
)
```

### Combining Multiple Survey Cycles

When combining cycles (e.g., two NHANES 2-year cycles), divide weights by the
number of cycles:

```r
# INTENT: Combine two NHANES cycles for adequate subgroup sample size
# REASONING: NHANES analytic guidelines require dividing 2-year weights
#   by the number of cycles to produce correct population estimates
# ASSUMES: Both cycles use the same design structure
combined <- rbind(cycle1, cycle2)
combined$wt_4yr <- combined$wtmec2yr / 2

des <- svydesign(
  ids = ~sdmvpsu,
  strata = ~sdmvstra,
  weights = ~wt_4yr,
  data = combined,
  nest = TRUE
)
```
