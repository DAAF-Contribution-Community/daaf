# survey Gotchas Reference

survey 4.5 on R 4.5.3 -- common pitfalls and their solutions.

---

## Contents

1. [WLS Is Not Survey-Weighted Regression](#wls-is-not-survey-weighted-regression)
2. [Lonely PSU Handling](#lonely-psu-handling)
3. [Subsetting: subset() vs. filter()](#subsetting-subset-vs-filter)
4. [Degrees of Freedom](#degrees-of-freedom)
5. [Weight Selection](#weight-selection)
6. [Quasi-Families in svyglm()](#quasi-families-in-svyglm)
7. [Missing Data (na.rm)](#missing-data-narm)
8. [Calibration Gotchas](#calibration-gotchas)
9. [Proportions via svymean()](#proportions-via-svymean)
10. [Comparison with Python svy](#comparison-with-python-svy)

---

## WLS Is Not Survey-Weighted Regression

This is the single most important gotcha in survey analysis. Base R `lm()` with
`weights =` performs weighted least squares (WLS), which is fundamentally
different from survey-weighted regression via `svyglm()`.

```r
# WRONG: WLS -- ignores stratification and clustering
fit_wrong <- lm(income ~ age + factor(gender), data = df, weights = wt)

# CORRECT: Survey-weighted regression
des <- svydesign(ids = ~psu, strata = ~strat, weights = ~wt,
                  data = df, nest = TRUE)
fit_correct <- svyglm(income ~ age + factor(gender), design = des)
```

### What Goes Wrong

| Aspect | lm(weights=) | svyglm() |
|--------|-------------|----------|
| Point estimates | Correct (weighted) | Correct (weighted) |
| Standard errors | **WRONG** (ignores design) | Correct (design-based) |
| p-values | **WRONG** (too small) | Correct |
| Confidence intervals | **WRONG** (too narrow) | Correct |
| Degrees of freedom | n - p | PSUs - strata |

The point estimates from WLS and survey regression are identical. But the SEs
from WLS are typically too small because they assume independent observations
with no stratification or clustering. This leads to artificially narrow CIs and
inflated significance.

### When WLS Is Appropriate

WLS (`lm(weights=)`) is appropriate when:
- The weights correct for heteroskedasticity (not sampling design)
- The data is NOT from a complex survey
- There is no clustering or stratification to account for

If the data has strata, PSU, and survey weights, always use `svyglm()`.

---

## Lonely PSU Handling

A "lonely PSU" (singleton stratum) occurs when a stratum has only one primary
sampling unit. This makes within-stratum variance undefined.

### Symptoms

```
Error in onestrat(x[index, , drop = FALSE], clusters[index], nPSU[i],  :
  Stratum (...) has only one PSU at stage 1
```

### Solutions

Set a global option before creating the design:

```r
# Option 1: "remove" -- drop lonely strata from variance computation
# (conservative: SEs are slightly too large)
options(survey.lonely.psu = "remove")

# Option 2: "adjust" -- center at grand mean instead of stratum mean
# (most common choice; equivalent to R's "certainty" for single PSU)
options(survey.lonely.psu = "adjust")

# Option 3: "certainty" -- treat as certainty stratum (zero variance)
# (only if the singleton is genuinely a certainty selection)
options(survey.lonely.psu = "certainty")

# Option 4: "average" -- use average of other strata's contributions
options(survey.lonely.psu = "average")
```

### Best Practice

```r
# Set at the top of every survey analysis script
options(survey.lonely.psu = "adjust")
```

`"adjust"` is the safest general-purpose choice. Document the choice with
`# REASONING:` comment.

### Prevention

- Avoid domain estimation on very rare subgroups
- Use replicate weights (which handle singletons implicitly)
- Collapse strata with few PSUs before analysis

---

## Subsetting: subset() vs. filter()

### The Rule

- Use `subset()` on the **design object** (correct)
- Never use `dplyr::filter()` on the raw data before creating a design (wrong)

```r
# CORRECT: subset the design
des_adult <- subset(des, age >= 18)

# WRONG: filter the data, then create design
# adult_data <- dplyr::filter(df, age >= 18)
# des_wrong <- svydesign(..., data = adult_data)
```

### Why

`subset()` on the design object zero-weights excluded observations but retains
the full PSU/strata structure for variance estimation. Filtering the data
removes PSUs from the design, potentially creating singleton strata and
producing incorrect SEs.

### Common Mistake: Using dplyr Verbs on Design Objects

Do not use `dplyr::filter()`, `dplyr::mutate()`, or other tidyverse verbs
directly on survey design objects. They do not understand the design structure.

```r
# WRONG: dplyr does not understand survey objects
# des_filtered <- dplyr::filter(des, age >= 18)

# CORRECT: use survey's subset()
des_filtered <- subset(des, age >= 18)
```

To add columns to a design object, modify `des$variables` directly:

```r
# Add a derived variable to the design
des$variables$age_squared <- des$variables$age^2
```

---

## Degrees of Freedom

### Design-Based vs. Model-Based

Survey regression uses design-based degrees of freedom:

```
df = (number of PSUs) - (number of strata)
```

This is typically much smaller than the model-based df = n - p used by `lm()`.
Smaller df means wider confidence intervals and larger p-values, especially for
surveys with few PSUs.

### Checking Degrees of Freedom

```r
# Degrees of freedom for the design
degf(des)

# For a model
fit <- svyglm(y ~ x, design = des)
summary(fit)  # reports df in the summary
```

### Impact

A survey with 50 strata and 100 PSUs has df = 100 - 50 = 50. Compare to
a sample of 10,000 observations with model-based df = 9,998. The critical
t-value at df = 50 is 2.01 vs. 1.96 at df = 9998. This difference is small for
means but can matter for rare subgroups with even fewer effective PSUs.

### Small-Sample Adjustments

For designs with very few df (< 30), consider:
- Reporting t-based CIs rather than z-based CIs
- Using the `Satterthwaite` approximation where available
- Being cautious about significance claims near the 0.05 threshold

---

## Weight Selection

### Multiple Weight Variables

Many surveys provide multiple weight variables for different analysis populations:

| Population | NHANES Weight |
|------------|---------------|
| Interview participants | `wtint2yr` |
| MEC examination participants | `wtmec2yr` |
| Fasting subsample | `wtsaf2yr` |
| Dietary day 1 | `wtdrd1` |

### The Rule

Use the weight corresponding to the most restrictive data collection component
required by your analysis variables.

```r
# If analyzing BMI (collected at MEC exam):
des <- svydesign(..., weights = ~wtmec2yr, ...)   # MEC weight

# If analyzing interview-only data:
des <- svydesign(..., weights = ~wtint2yr, ...)    # Interview weight

# WRONG: using interview weight for exam variables
# des <- svydesign(..., weights = ~wtint2yr, ...)  # BIASED for MEC variables
```

### Cross-Component Analysis

If your analysis uses variables from different components (e.g., interview
income + exam BMI), use the weight for the most restrictive component (in
NHANES: the exam weight, since not all interviewees were examined).

---

## Quasi-Families in svyglm()

### Why Quasi-Families

When fitting binomial or Poisson models on weighted data, R produces warnings:

```
Warning: non-integer #successes in a binomial glm!
Warning: non-integer counts in a Poisson glm!
```

These warnings occur because the weighted data creates non-integer "counts."
They are harmless -- the estimates are correct -- but can clutter output and
cause confusion.

### Solution: Use Quasi-Families

```r
# Instead of binomial(), use quasibinomial()
fit <- svyglm(y ~ x, design = des, family = quasibinomial())

# Instead of poisson(), use quasipoisson()
fit <- svyglm(count ~ x, design = des, family = quasipoisson())
```

The point estimates and SEs are identical between `binomial()` and
`quasibinomial()` in `svyglm()`. The quasi-family just suppresses the
misleading warnings.

### Gaussian Does Not Need Quasi

For continuous outcomes, use `gaussian()` directly -- no quasi variant needed.

---

## Missing Data (na.rm)

### The Problem

Without `na.rm = TRUE`, any NA in the analysis variable makes the entire
estimate NA:

```r
# Returns NA if ANY income value is missing
svymean(~income, design = des)              # NA!

# Drops NAs before computing
svymean(~income, design = des, na.rm = TRUE)  # works
```

### Best Practice

Always use `na.rm = TRUE` for estimation functions. Document the missingness
assumption:

```r
# ASSUMES: Observations with missing income are MCAR or MAR;
#   dropping them does not bias the weighted estimate
svymean(~income, design = des, na.rm = TRUE)
```

### Checking Missingness

```r
# Count NAs in a variable
sum(is.na(des$variables$income))

# Missingness rate
mean(is.na(des$variables$income))
```

If missingness is > 10% or appears non-random, document this as a limitation
in the analysis.

---

## Calibration Gotchas

### Calibration on Public-Use Files

Most public-use files from federal surveys already have calibrated weights.
Re-calibrating is usually unnecessary and can introduce errors.

Only calibrate if:
- You have raw sampling weights (base weights) that need adjustment
- You need to adjust for a specific target population not covered by the
  provided weights
- The survey documentation explicitly instructs you to calibrate

### calibrate() vs. postStratify() vs. rake()

| Function | When to Use |
|----------|-------------|
| `postStratify()` | Adjust to marginal totals of one variable |
| `rake()` | Adjust to marginal totals of multiple variables (iterative) |
| `calibrate()` | General calibration with continuous or categorical variables |

```r
# Post-stratification
pop_totals <- data.frame(
  gender = c("Male", "Female"),
  Freq = c(160e6, 165e6)
)
des_cal <- postStratify(des, ~gender, pop_totals)

# Raking
des_raked <- rake(des,
  list(~gender, ~age_group),
  list(gender_pop, age_pop)
)
```

### Common Calibration Mistake

Do not calibrate with variables that have missing values. NAs in the calibration
variable will cause errors or silently produce incorrect weights.

---

## Proportions via svymean()

### The Gotcha

`svymean()` on a numeric 0/1 variable gives the mean (which equals the
proportion), but without proper labeling:

```r
# Gives proportion but labeled as "mean"
svymean(~employed, design = des)

# Better: wrap in factor() for labeled proportions
svymean(~factor(employed), design = des)
```

### Multi-Category Variables

For multi-category variables, you must use `factor()`:

```r
# WRONG: treats education as numeric, computes mean of codes
# svymean(~education_code, design = des)

# CORRECT: treats as categorical, computes proportion per level
svymean(~factor(education_code), design = des)
```

---

## Comparison with Python svy

Key differences between R survey and Python svy for users working across both
languages.

| Feature | R survey | Python svy |
|---------|---------|-----------|
| Design object | `svydesign()` (one call) | `svy.Design()` + `svy.Sample()` (two objects) |
| Variable specification | Formula (`~var`) | String (`"var"`) |
| Categorical in regression | `factor(var)` in formula | `svy.Cat("var")` |
| Domain estimation | `svyby(~var, ~group, des, svymean)` | `sample.estimation.mean("var", by="group")` |
| Subsetting | `subset(des, condition)` | Pre-filter data (limited in v0.13.0) |
| Quasi-families | `quasibinomial()`, `quasipoisson()` | Handled internally by `family="binomial"` |
| Ordinal logistic | `svyolr()` | Not available |
| Cox PH | `svycoxph()` | Not available |
| FPC | Fully functional | Non-functional in v0.13.0 |
| Lonely PSU | `options(survey.lonely.psu = ...)` | `sample.singleton.*()` methods |
| Data format | Base R data.frame | Polars DataFrame |
| Replicate weights | `svrepdesign()` | `svy.RepWeights()` + `svy.Design()` |

### Key Advantage: R survey Has More Model Types

R's survey package supports ordinal logistic (`svyolr`), Cox PH (`svycoxph`),
and quasi-families natively. Python's svy is limited to gaussian, binomial, and
poisson. For unsupported models in Python, the svy skill recommends using rpy2 to
call R's survey package -- which is exactly what this skill documents.
