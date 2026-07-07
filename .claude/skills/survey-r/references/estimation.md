# survey Estimation Reference

survey 4.5 on R 4.5.3 -- syntax and library guidance only.

---

## Contents

1. [Point Estimates and Standard Errors](#point-estimates-and-standard-errors)
2. [Proportions](#proportions)
3. [Ratios](#ratios)
4. [Quantiles and Medians](#quantiles-and-medians)
5. [Domain Estimation with svyby()](#domain-estimation-with-svyby)
6. [Custom Contrasts with svycontrast()](#custom-contrasts-with-svycontrast)
7. [Design Effects (DEFF)](#design-effects-deff)
8. [Cross-Tabulations](#cross-tabulations)
9. [Survey Chi-Squared Tests](#survey-chi-squared-tests)
10. [Extracting Results for Reporting](#extracting-results-for-reporting)
11. [Common Patterns and Pitfalls](#common-patterns-and-pitfalls)

---

## Point Estimates and Standard Errors

### svymean() -- Population Means

```r
# Single variable
mn <- svymean(~income, design = des, na.rm = TRUE)
print(mn)            # point estimate + SE
coef(mn)             # extract point estimate only
SE(mn)               # extract SE only
confint(mn)          # 95% CI

# Multiple variables simultaneously
mn_multi <- svymean(~income + age + bmi, design = des, na.rm = TRUE)
print(mn_multi)
```

### svytotal() -- Population Totals

```r
# Estimated population total
tot <- svytotal(~enrollment, design = des, na.rm = TRUE)
print(tot)
coef(tot)
SE(tot)
confint(tot)
```

### When to Use Totals vs. Means

- **Totals** for aggregate quantities: total enrollment, total expenditure
- **Means** for per-unit averages: mean income, mean test score
- **Proportions** for categorical shares: percent employed, percent below poverty

---

## Proportions

There is no separate `svyprop()` function. Proportions are estimated via
`svymean()` on factor variables.

```r
# Proportions of a binary variable
svymean(~factor(employed), design = des, na.rm = TRUE)

# Proportions across all categories
svymean(~factor(education_level), design = des, na.rm = TRUE)
```

### Proportion with CI

```r
prop <- svymean(~factor(employed), design = des, na.rm = TRUE)
confint(prop)
```

### Alternative: svyciprop() for Exact CI Methods

```r
# Exact confidence interval for a single proportion
# Methods: "logit", "likelihood", "asin", "beta", "mean", "xlogit"
svyciprop(~I(employed == 1), design = des, method = "logit")
```

`svyciprop()` provides alternative CI computation methods that can be more
accurate for proportions near 0 or 1. The default Wald CI from `svymean()` is
fine for proportions in the 0.1-0.9 range.

---

## Ratios

### svyratio() -- Ratio Estimation

```r
# Ratio of two survey variables
rat <- svyratio(
  numerator = ~total_expenditure,
  denominator = ~household_size,
  design = des,
  na.rm = TRUE
)
print(rat)
confint(rat)
```

### Why Use svyratio() Instead of Deriving the Ratio First

Do not compute `expenditure / household_size` as a new column and then estimate
its mean. This produces incorrect SEs because it ignores the covariance between
numerator and denominator.

```r
# WRONG: pre-computing the ratio
# df$per_capita <- df$expenditure / df$hh_size
# svymean(~per_capita, design = des)  # <-- incorrect SEs

# CORRECT: use ratio estimation
svyratio(~expenditure, ~hh_size, design = des)  # <-- correct SEs
```

### Domain Ratios

```r
# Ratio by subgroup
svyby(~expenditure, ~region, design = des,
      svyratio, denominator = ~hh_size, na.rm = TRUE)
```

---

## Quantiles and Medians

```r
# Median (50th percentile)
med <- svyquantile(~income, design = des, quantiles = 0.5, na.rm = TRUE)
print(med)

# Multiple quantiles
quants <- svyquantile(~income, design = des,
                       quantiles = c(0.10, 0.25, 0.50, 0.75, 0.90),
                       na.rm = TRUE)
print(quants)
```

### CI Method for Quantiles

```r
# The ci argument controls CI computation for quantiles
svyquantile(~income, design = des, quantiles = 0.5,
            ci = TRUE, na.rm = TRUE)
```

Quantile SEs are typically larger than mean SEs. For replicate weight designs,
quantile variance estimation is more straightforward than for Taylor
linearization designs.

---

## Domain Estimation with svyby()

Domain estimation computes statistics for subgroups while preserving the full
survey design.

### Basic Domain Estimation

```r
# Mean income by gender
result <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
print(result)

# Mean by education level
result <- svyby(~income, ~education, design = des, svymean, na.rm = TRUE)
print(result)
```

### Multiple Analysis Variables

```r
# Multiple outcome variables by one grouping variable
result <- svyby(~income + age + bmi, ~gender, design = des,
                svymean, na.rm = TRUE)
print(result)
```

### Multiple Grouping Variables

```r
# Cross-classified domains
result <- svyby(~income, ~gender + education, design = des,
                svymean, na.rm = TRUE)
print(result)
```

### Domain Totals

```r
# Totals by subgroup
result <- svyby(~enrollment, ~region, design = des, svytotal, na.rm = TRUE)
print(result)
```

### Domain Quantiles

```r
# Median income by gender
result <- svyby(~income, ~gender, design = des,
                svyquantile, quantiles = 0.5, ci = TRUE, na.rm = TRUE)
print(result)
```

### Why svyby() Instead of Pre-Filtering

Never pre-filter the data for domain estimation. Pre-filtering removes PSUs
and strata needed for correct variance estimation.

```r
# WRONG: filter then estimate -- breaks the design structure
# females <- subset(data, gender == "Female")
# des_f <- svydesign(ids = ~psu, strata = ~strat, weights = ~wt, data = females)
# svymean(~income, des_f)  # <-- WRONG SEs

# CORRECT: use svyby() or subset() on the design object
svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
# or: svymean(~income, design = subset(des, gender == "Female"))
```

Pre-filtering the raw data and creating a new design object from the filtered
data can: (1) produce incorrect variance estimates, (2) create singleton PSU
problems, and (3) change degrees of freedom. The `svyby()` function and
`subset()` on the design object handle this correctly.

---

## Custom Contrasts with svycontrast()

`svycontrast()` computes linear and nonlinear combinations of survey statistics
with correct variance estimation via the delta method.

### Linear Contrasts

```r
# Difference between two domain means
domain_means <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)

# Contrast: Male mean minus Female mean
diff <- svycontrast(domain_means, list(diff = c(-1, 1)))
print(diff)
confint(diff)
```

### Named Contrasts

```r
# Multiple contrasts at once
domain_means <- svyby(~income, ~education, design = des, svymean,
                       na.rm = TRUE)
# Suppose education has levels: "HS", "BA", "MA"
contrasts <- svycontrast(domain_means, list(
  ba_vs_hs = c(-1, 1, 0),
  ma_vs_hs = c(-1, 0, 1),
  ma_vs_ba = c(0, -1, 1)
))
print(contrasts)
```

### Nonlinear Contrasts (Ratio of Means)

```r
# Ratio of two domain means using quote()
domain_means <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
ratio <- svycontrast(domain_means, quote(Female / Male))
print(ratio)
```

### Using svycontrast() as emmeans Alternative

Since `emmeans` is not installed, use `svycontrast()` for pairwise comparisons
from regression models:

```r
# Fit survey regression
fit <- svyglm(income ~ factor(education), design = des)

# Get coefficients (intercept = reference level mean, others = differences)
# For pairwise comparisons, construct contrasts manually
coefs <- coef(fit)
vcv <- vcov(fit)

# Or compute predicted means at each level and contrast them
# See regression.md for the full pattern
```

---

## Design Effects (DEFF)

The design effect measures how much the complex design inflates (or deflates)
variance compared to a simple random sample.

```r
# DEFF is included in svymean() output via deff = TRUE
mn <- svymean(~income, design = des, na.rm = TRUE, deff = TRUE)
print(mn)
# Output includes: mean, SE, DEFF

# Extract DEFF value
deff(mn)
```

### Interpreting DEFF

- **DEFF = 1.0**: Complex design is as efficient as SRS
- **DEFF > 1.0**: Clustering increases variance (common)
- **DEFF < 1.0**: Stratification decreases variance
- **Typical range**: 1.5 to 5.0 for clustered household surveys

### Effective Sample Size

```r
# n_eff = n / DEFF
n_actual <- nrow(des$variables)   # or nrow(data)
deff_val <- deff(svymean(~income, design = des, na.rm = TRUE, deff = TRUE))
n_eff <- n_actual / deff_val
cat("Effective sample size:", round(n_eff), "\n")
```

Report DEFF alongside estimates. A survey of 10,000 with DEFF = 4.0 has the
precision of an SRS of only 2,500.

---

## Cross-Tabulations

### svytable() -- Weighted Contingency Tables

```r
# Weighted cross-tabulation
tab <- svytable(~gender + education, design = des)
print(tab)
```

`svytable()` produces estimated population counts (not sample counts). For
proportions, use `svymean()` with interaction of factors.

### Proportional Cross-Tab

```r
# Proportions in a cross-tabulation
prop_tab <- svymean(~interaction(gender, education), design = des)
print(prop_tab)
```

---

## Survey Chi-Squared Tests

### svychisq() -- Design-Adjusted Chi-Squared

```r
# Test of independence between two categorical variables
test <- svychisq(~gender + education, design = des)
print(test)
```

The survey chi-squared test adjusts for the complex design. The default uses a
Rao-Scott correction, which converts the Pearson chi-squared statistic to an
F-statistic with design-based degrees of freedom.

### Test Statistics Available

```r
# statistic argument controls the test type
svychisq(~gender + education, design = des, statistic = "F")        # default
svychisq(~gender + education, design = des, statistic = "Chisq")    # Pearson
svychisq(~gender + education, design = des, statistic = "Wald")     # Wald test
svychisq(~gender + education, design = des, statistic = "adjWald")  # adjusted Wald
```

---

## Extracting Results for Reporting

### From svymean() / svytotal()

```r
mn <- svymean(~income + age, design = des, na.rm = TRUE)

# As a data frame
data.frame(
  variable = names(coef(mn)),
  estimate = coef(mn),
  se = SE(mn),
  ci_low = confint(mn)[, 1],
  ci_high = confint(mn)[, 2]
)
```

### From svyby()

```r
result <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)

# svyby results are already data frames
print(result)
# Columns: gender, income, se (se.income)
confint(result)
```

### Using broom::tidy() with Survey Objects

`broom` can tidy some survey objects:

```r
library(broom)

# tidy() works on svyglm objects
fit <- svyglm(income ~ age + factor(gender), design = des)
tidy(fit, conf.int = TRUE)
glance(fit)
```

For estimation objects (`svymean`, `svytotal`), manual extraction (shown above)
is more reliable than `tidy()`.

---

## Common Patterns and Pitfalls

### Pattern: Complete Estimation Workflow

```r
# --- Config ---
library(survey)
library(arrow)

# --- Load ---
data <- read_parquet("data/raw/nhanes_demo.parquet")

# --- Design ---
# INTENT: NHANES complex multi-stage design
# REASONING: Standard NHANES design variables
# ASSUMES: MEC-examined subsample
des <- svydesign(ids = ~sdmvpsu, strata = ~sdmvstra,
                  weights = ~wtmec2yr, data = data, nest = TRUE)

# --- Estimate ---
# Overall mean
mn <- svymean(~bmxbmi, design = des, na.rm = TRUE)
cat("Mean BMI:", round(coef(mn), 2), "(SE:", round(SE(mn), 4), ")\n")
cat("95% CI:", round(confint(mn)[1], 2), "to",
    round(confint(mn)[2], 2), "\n")

# By gender
by_gender <- svyby(~bmxbmi, ~riagendr, design = des, svymean, na.rm = TRUE)
cat("\nBy gender:\n")
print(by_gender)

# DEFF
mn_deff <- svymean(~bmxbmi, design = des, na.rm = TRUE, deff = TRUE)
cat("\nDEFF:", round(deff(mn_deff), 2), "\n")

# --- Validate ---
cat("\nSample size:", nrow(data), "\n")
cat("Design df:", degf(des), "\n")
stopifnot(nrow(data) > 0)
```

### Pitfall: Using Unweighted Statistics

Never use `mean(df$income)` or `table(df$gender)` on survey data. Unweighted
statistics are biased for the target population and have incorrect SEs.

### Pitfall: Forgetting na.rm = TRUE

Without `na.rm = TRUE`, any NA produces NA estimates. Always include it and
document the assumption about missingness.

### Pitfall: Pre-Filtering Instead of Domain Estimation

Always use `svyby()` or `subset()` on the design object, never on the raw data.
See the domain estimation section for details.
