# survey Domain Estimation Reference

survey 4.5 on R 4.5.3 -- syntax and library guidance only.

---

## Contents

1. [Why Domain Estimation Matters](#why-domain-estimation-matters)
2. [svyby() -- The Primary Domain Tool](#svyby----the-primary-domain-tool)
3. [subset() on Design Objects](#subset-on-design-objects)
4. [Interaction Domains](#interaction-domains)
5. [Domain Estimation vs. Data Filtering](#domain-estimation-vs-data-filtering)
6. [Patterns for Common Domain Tasks](#patterns-for-common-domain-tasks)

---

## Why Domain Estimation Matters

Domain (subpopulation) estimation is the correct way to compute statistics for
subgroups of a survey population. The critical insight: even when you only want
estimates for one subgroup, the variance estimation requires information from the
full survey design.

If you filter the raw data before creating the design object, you lose PSUs and
strata that contribute to variance estimation. This produces:
1. Incorrect standard errors (usually too small)
2. Singleton PSU problems (strata with only one PSU after filtering)
3. Wrong degrees of freedom

---

## svyby() -- The Primary Domain Tool

`svyby()` computes survey statistics by one or more grouping variables while
preserving the full design structure.

### Syntax

```r
svyby(
  formula,          # ~outcome_variable(s)
  by,               # ~grouping_variable(s)
  design,           # survey design object
  FUN,              # estimation function (svymean, svytotal, etc.)
  ...               # additional arguments passed to FUN
)
```

### Mean by Group

```r
# Mean income by gender
svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)

# Mean income by education level
svyby(~income, ~education, design = des, svymean, na.rm = TRUE)
```

### Total by Group

```r
# Total enrollment by region
svyby(~enrollment, ~region, design = des, svytotal, na.rm = TRUE)
```

### Proportion by Group

```r
# Proportions of employment status by gender
svyby(~factor(employed), ~gender, design = des, svymean, na.rm = TRUE)
```

### Multiple Outcome Variables

```r
# Multiple outcomes by one grouping variable
svyby(~income + age + bmi, ~gender, design = des, svymean, na.rm = TRUE)
```

### CIs from svyby()

```r
result <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
confint(result)
```

---

## subset() on Design Objects

`subset()` applied to a design object creates a subsetted design that preserves
the full sampling structure for variance estimation. Use this for:
- Restricting to a subpopulation before analysis
- Domain-specific regression (see `regression.md`)

```r
# Subset the design to adults aged 18+
des_adult <- subset(des, age >= 18)

# Now all estimation uses only adults but with correct SEs
svymean(~income, design = des_adult, na.rm = TRUE)
svyglm(income ~ education, design = des_adult)
```

### subset() vs. svyby()

| Task | Use This |
|------|----------|
| Same statistic across all levels of a grouping variable | `svyby()` |
| Restrict analysis to one specific subgroup | `subset()` |
| Domain-specific regression | `subset()` on design, then `svyglm()` |
| Comparing groups | `svyby()` + `svycontrast()` |

### Key: NEVER Filter Raw Data

```r
# WRONG -- breaks the design
# filtered <- df[df$age >= 18, ]
# des_wrong <- svydesign(ids = ~psu, strata = ~strat, weights = ~wt,
#                         data = filtered, nest = TRUE)

# CORRECT -- subset the design object
des_correct <- subset(des, age >= 18)
```

The difference: `subset()` on the design object retains the full set of PSUs and
strata in the variance estimation, zero-weighting excluded observations.
Filtering the raw data removes PSUs entirely, changing the design structure.

---

## Interaction Domains

### Cross-Classified Groups

```r
# Mean income by gender x education (all combinations)
svyby(~income, ~gender + education, design = des, svymean, na.rm = TRUE)
```

### Creating an Interaction Variable

For more control, create an explicit interaction variable:

```r
# Create combined group variable
des$variables$group <- interaction(
  des$variables$gender,
  des$variables$education,
  drop = TRUE
)

# Domain estimation by the interaction
svyby(~income, ~group, design = des, svymean, na.rm = TRUE)
```

### Contrasts Across Interaction Domains

```r
# Compare specific cells of the interaction
result <- svyby(~income, ~gender + education, design = des, svymean,
                 na.rm = TRUE)

# Contrast: Male BA vs Female BA
# (requires knowing the row order in the result)
svycontrast(result, list(
  male_ba_vs_female_ba = c(0, 0, 1, 0, -1, 0)  # adjust indices
))
```

For complex contrasts, it is often clearer to use `subset()` plus separate
estimates with manual delta-method calculations, or to use `svyglm()` with
interaction terms.

---

## Domain Estimation vs. Data Filtering

### The Fundamental Rule

**For descriptive statistics (means, totals, proportions):** Use `svyby()` or
`subset()` on the design object. Never filter the raw data.

**For regression:** Use `subset()` on the design object.

### Why Filtering Is Wrong

Consider a stratified design with 3 strata, each with 2 PSUs:

```
Stratum A: PSU 1 (50 obs), PSU 2 (45 obs)
Stratum B: PSU 1 (60 obs), PSU 2 (55 obs)
Stratum C: PSU 1 (40 obs), PSU 2 (35 obs)
```

If you filter to males only and Stratum C PSU 2 has no males:
- Stratum C becomes a "lonely PSU" stratum (only 1 PSU)
- Within-stratum variance for Stratum C is undefined
- The estimate either fails or uses a lonely PSU adjustment

With `subset()` on the design, Stratum C PSU 2 is kept with zero weight for
males, so the stratum still has 2 PSUs and variance estimation is correct.

### When Data Filtering Is Acceptable

The only case where filtering raw data before `svydesign()` is acceptable:
- You are completely excluding a **population** (not a domain), and
- The excluded population was sampled independently with its own design

For example, excluding the child sample from an adult+child survey where the two
samples have completely separate designs. This is rare.

---

## Patterns for Common Domain Tasks

### Pattern 1: Age-Restricted Analysis

```r
# INTENT: Analyze adults aged 20+ only
# REASONING: subset() preserves full design for variance estimation
des_adult <- subset(des, age >= 20)
svymean(~bmi, design = des_adult, na.rm = TRUE)
```

### Pattern 2: Comparing Two Groups

```r
# INTENT: Compare mean income between men and women
# REASONING: svyby + svycontrast gives design-based difference with SE
# ASSUMES: gender has alphabetical levels (Female, Male), so svyby rows are
#   ordered Female first — contrast coefficients follow that row order
#   (verified: c(1, -1) computes first-level MINUS second-level)
by_gender <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
diff <- svycontrast(by_gender, list(male_minus_female = c(-1, 1)))
cat("Difference:", coef(diff), "SE:", SE(diff), "\n")
confint(diff)
```

### Pattern 3: Multiple Outcomes by Multiple Groups

```r
# INTENT: Profile demographics by region
result <- svyby(
  ~income + age + bmi,
  ~region,
  design = des,
  svymean,
  na.rm = TRUE
)
print(result)
```

### Pattern 4: Proportions Within Domains

```r
# INTENT: Employment proportions by education level
prop_by_edu <- svyby(
  ~factor(employed),
  ~education,
  design = des,
  svymean,
  na.rm = TRUE
)
print(prop_by_edu)
```

### Pattern 5: Domain-Specific Regression

```r
# INTENT: Income model for adults with college education
# REASONING: subset on design preserves structure; svyglm uses correct SEs
des_college <- subset(des, education == "College")
fit <- svyglm(income ~ age + factor(gender), design = des_college)
summary(fit)
```
